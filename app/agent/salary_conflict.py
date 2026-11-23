"""Compare explicit fixed pay in the posting body and a structured salary column."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from .evidence import is_instruction


_PERIODS = {"연봉": "year", "연간": "year", "연": "year", "월급": "month", "월봉": "month",
            "월간": "month", "월": "month"}
_PAY_LABEL = r"연봉|월급|월봉|급여\s*조건|급여|보수|임금"
_HEADER = re.compile(rf"(?P<label>{_PAY_LABEL})(?:\s*\(\s*(?P<unit>만\s*원|원)\s*\))?")
_BODY = re.compile(rf"(?:[-*•]\s+)?(?P<label>{_PAY_LABEL})(?:은|는)?[\s:：=]+(?P<pay>.+)")
_NUMBER = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?"
_KOREAN_NUMBER = r"(?:[1-9]천(?:\s*[1-9]백)?(?:\s*[1-9]십)?|[1-9]백(?:\s*[1-9]십)?)"
_AMOUNT = re.compile(
    rf"(?:(?P<period>{'|'.join(_PERIODS)})\s*[:：]?\s*)?"
    rf"(?P<number>{_NUMBER}|{_KOREAN_NUMBER})\s*(?P<unit>만\s*원|원)?"
    r"\s*(?:입니다|이다)?[.。]?"
)
_TABLE_RULE = re.compile(r":?-{3,}:?")


@dataclass(frozen=True)
class _Quote:
    annual: Decimal
    monthly_step: Decimal
    text: str


def _quotes_agree(first: _Quote, second: _Quote) -> bool:
    if bool(first.monthly_step) == bool(second.monthly_step):
        return first.annual == second.annual
    # Allow for display rounding only across pay periods.
    return abs(first.annual - second.annual) <= max(first.monthly_step, second.monthly_step)


def _quote(text: str, label: str, evidence: str, default_unit: str | None = None) -> _Quote | None:
    match = _AMOUNT.fullmatch(text)
    if match is None:
        return None
    period = _PERIODS.get(match["period"]) or _PERIODS.get(label)
    unit = match["unit"] or default_unit
    if not period or not unit:
        return None
    number = match["number"].replace(",", "")
    if number[-1] in "천백십":
        scales = {"천": 1000, "백": 100, "십": 10}
        value = Decimal(sum(int(digit) * scales[place] for digit, place in re.findall(r"([1-9])([천백십])", number)))
    else:
        value = Decimal(number)
    scale = 1 if unit == "원" else 10_000
    won = value * scale
    if won <= 0:
        return None
    if period == "year":
        return _Quote(won, Decimal(0), evidence)
    # A monthly figure may be rounded to the last displayed place.
    return _Quote(won * 12, Decimal(scale * 12).scaleb(value.as_tuple().exponent), evidence)


def _table_cells(line: str) -> list[str]:
    if "|" in line:
        return [cell.strip().strip("*") for cell in line.removeprefix("|").removesuffix("|").split("|")]
    return [cell.strip() for cell in line.split("\t")]


def find_salary_conflict(masked_source: str) -> list[str]:
    """Return two verbatim source lines when each side states a different fixed salary."""
    body: list[_Quote] = []
    table: list[_Quote] = []
    column = None
    for line in masked_source.splitlines():
        line = line.strip()
        cells = _table_cells(line)
        if len(cells) < 2:
            column = None
            match = _BODY.fullmatch(line)
            if match and not is_instruction(line):
                quote = _quote(match["pay"].strip(), match["label"], line)
                if quote:
                    body.append(quote)
            continue

        headers = [(i, m) for i, cell in enumerate(cells) if (m := _HEADER.fullmatch(cell))]
        if headers:
            column = (*headers[0], len(cells)) if len(headers) == 1 else None
        elif column and len(cells) == column[2] and not is_instruction(line):
            i, header, _ = column
            if not _TABLE_RULE.fullmatch(cells[i]):
                quote = _quote(cells[i], header["label"], line, header["unit"])
                if quote:
                    table.append(quote)
        else:
            column = None

    if len({q.annual for q in body}) != 1 or len({q.annual for q in table}) != 1:
        return []
    if any(_quotes_agree(a, b) for a in body for b in table):
        return []
    return [body[0].text, table[0].text]
