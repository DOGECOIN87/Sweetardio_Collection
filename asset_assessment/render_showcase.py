#!/usr/bin/env python3
"""Render one token per character against its chosen showcase background.

Pairings live in catalog/character_showcase/pairings.json; see the README there
for how they were picked. Every character gets a different plate.

Usage (from repo root): python3 asset_assessment/render_showcase.py [outdir] [seed]
"""
import os,sys,json,random
sys.path.insert(0,"/home/user/Sweetardio_Collection"); os.chdir("/home/user/Sweetardio_Collection")
from PIL import Image, ImageDraw, ImageFont
import generator
from generator import create_image, generate_random_combination
OUT_DEFAULT="catalog/character_showcase"
assign=json.load(open(os.path.join(OUT_DEFAULT,"pairings.json")))
outdir=sys.argv[1] if len(sys.argv)>1 else OUT_DEFAULT
seed=int(sys.argv[2]) if len(sys.argv)>2 else 11
SP=outdir
os.makedirs(outdir,exist_ok=True)
def fnt(s):
    try: return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",s)
    except OSError: return ImageFont.load_default()
CS=330; LH=26; COLS=7
items=sorted(assign.items())
rows=(len(items)+COLS-1)//COLS
sheet=Image.new("RGB",(COLS*CS,rows*(CS+LH)),(18,18,22)); d=ImageDraw.Draw(sheet); f=fnt(12)
for i,(ch,v) in enumerate(items):
    random.seed(seed+i*17)
    layers,_=generate_random_combination(force_bg=("backgroundz",v["plate"]),
        force_arm=None, force_wat=None, force_sticker=None, force_char=ch)
    p=os.path.join(outdir,f"{ch}.png")
    Image.open(create_image(layers,output_name=p)).load()
    im=Image.open(p)
    x=(i%COLS)*CS; y=(i//COLS)*(CS+LH)
    sheet.paste(im.convert("RGB").resize((CS,CS),Image.LANCZOS),(x,y))
    d.text((x+4,y+CS+3),ch[:30],font=f,fill=(235,235,235))
    d.text((x+4,y+CS+14),v["plate"][:32],font=f,fill=(140,180,220))
sheet.save(os.path.join(outdir,"_contact_sheet.png")); print("ok ->",outdir)
