# Historical website mockups

These files preserve the presentation lead's pre-rename website studies.
They are composed mockups, including hand-placed people, light and chrome;
they are not native play captures or current acceptance tools.

Their original source and imports are intentionally retained. Reproduce
them in an isolated checkout of the pre-R1 revision
`7597dce6f1263a27421c51ec97cff1b0b91b6f68`, with that revision's Python
package and content. Do not run them against the renamed current package
or add an import shim for them. Their old scratch filenames also belong
to that historical reproduction, not current proof storage.

R1 does not update the website or banner art. The presentation lead owns
that later work. Current native title evidence uses
`scripts/accept_r1_netbbs.py` and the R1 review packet instead.

The `karst_maps` generators don't import the package, so they run as they
are. In phase 5 of the rename, the city map's title block and the corner
line of Karst by Ringlight were changed to KARST 41 and both maps were
regenerated with `python render.py`. The banner title was edited by
`scripts/presentation_mockups/banner_retitle.py`.
