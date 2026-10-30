import referans_tara as R
t='''<div id="pid_55" class="post"><span class="largetext"><a href="u">Ali Kaan</a></span></div>
<div class="post_body" id="pid_55x"><img src="/attachment.php?aid=9" alt="">
&gt; 12-344 / 06 DY 1184 &gt; 340 &gt; Kızılay<br />
<img src="images/smilies/smile.png" class="smilie"><img src="https://x.test/a.jpg">
&gt; 09-618 &gt; 593 &gt; Ulus</div><div class="post_foot"></div>'''
t=t.replace("&gt;",">")
r=list(R.satirlar_foto(t,"https://forum.ulasimplatformu.com/showthread.php?tid=1&page=2"))
ok=len(r)==2 and r[0][1].endswith("/attachment.php?aid=9") and r[1][1]=="https://x.test/a.jpg" and r[0][3]=="Ali Kaan" and r[0][2].endswith("#pid55")
print(r); print("✓ foto ayıklama" if ok else "✗ foto ayıklama"); raise SystemExit(0 if ok else 1)
