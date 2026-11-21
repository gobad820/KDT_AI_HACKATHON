#!/bin/sh
# 렌더 프레임(media/printer/frames) → 첫 화면 영상·포스터·타임라인 (app/web/img/hero_print.*)
# 순서: render_hero.py 로 프레임을 만든 뒤 이 스크립트를 실행한다.
set -e
cd "$(dirname "$0")/../.."
F=media/printer/frames
FPS=$(python3 -c "import json;print(json.load(open('$F/timeline.json'))['fps'])")
WANT=$(python3 -c "import json;print(json.load(open('$F/timeline.json'))['frames'])")
HAVE=$(ls "$F"/f_*.png | wc -l | tr -d ' ')
[ "$HAVE" = "$WANT" ] || { echo "프레임 $HAVE/$WANT 장: 렌더가 끝나지 않았다"; exit 1; }
STILL=$(python3 -c "import json;t=json.load(open('$F/timeline.json'));print('%04d' % round(t['pauseAt']*t['fps']))")
ffmpeg -y -loglevel error -framerate "$FPS" -i "$F/f_%04d.png" \
  -vf "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p" \
  -c:v libx264 -preset slow -crf 22 -g 30 -movflags +faststart \
  -color_primaries bt709 -color_trc iec61966-2-1 -colorspace bt709 -color_range tv \
  app/web/img/hero_print.mp4
cwebp -quiet -q 88 "$F/f_0000.png" -o app/web/img/hero_print_poster.webp          # 재생 전: 빈 프린터
cwebp -quiet -q 88 "$F/f_$STILL.png" -o app/web/img/hero_print_still.webp         # 재생 못 할 때: 출력이 끝난 장면
python3 - "$F/timeline.json" app/web/img/hero_print.json <<'PY'
import json, sys
t = json.load(open(sys.argv[1]))
json.dump({k: t[k] for k in ("fps", "duration", "pauseAt", "tossAt")}, open(sys.argv[2], "w"))
PY
ls -la app/web/img/hero_print*
