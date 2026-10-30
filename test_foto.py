import forum_foto as F
h='''<div class="framio-image-container"><img src="https://images.ulasimarsiv.com/a/x.webp?w=1024" alt="MAN Lion's Classic CNG (A74 - SL313) - 07-553 | 06 BF 6434" class="s"></div><img src="https://i/y.webp" alt="logo">'''
r=F.fotolar(h)
ok=r==[("https://images.ulasimarsiv.com/a/x.webp?w=1024","MAN Lion's Classic CNG (A74 - SL313)","07-553","06 BF 6434")]
print(r);print("✓ foto ayıklama" if ok else "✗ foto ayıklama");raise SystemExit(0 if ok else 1)
