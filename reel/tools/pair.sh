#!/bin/sh
# render closed + open and put them side by side:  tools/pair.sh name ["extra=query"]
export NODE_PATH=$(npm root -g)
node tools/render_still.mjs closed out/$1_closed.png "$2" && node tools/render_still.mjs open out/$1_open.png "$2" && python3 -c "
from PIL import Image
a=Image.open('out/$1_closed.png'); b=Image.open('out/$1_open.png')
c=Image.new('RGB',(a.width*2,a.height)); c.paste(a,(0,0)); c.paste(b,(a.width,0)); c.save('out/$1_pair.png')"
