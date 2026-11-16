#!/bin/bash
# M10's integration note 4 (the upstream report on PyQt6 6.12.1's stubs): the PyQt mailing list's public archive,
# read again. Each message's archive page is fetched into a new, empty scratch folder; only its subject, author's
# name, date and the first lines of its body are kept here, never an address (lines with "@" or "<name> at <domain>"
# are dropped). Nothing is posted.
#   bash docs/delivery/reports/m10/wave5/observe-stub-report.sh > docs/delivery/reports/m10/wave5/stub-report.log 2>&1
S=C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad
D=$S/pyqt-archive-$$
BASE=https://www.riverbankcomputing.com/pipermail/pyqt/2026-November
rm -rf "$D" && mkdir -p "$D"
echo "# The PyQt mailing list's archive, read $(date -u +%Y-%m-%dT%H:%M:%SZ) (curl $(curl --version | head -1 | cut -d' ' -f2), no addresses kept)"
for n in 046574 046578 046579; do
  curl -s -A "Mozilla/5.0 (generic client)" -o "$D/$n.html" "$BASE/$n.html"; code=$?
  text=$(sed -e 's/<[^>]*>//g' -e 's/&gt;/>/g' -e 's/&lt;/</g' -e 's/&quot;/"/g' "$D/$n.html" | grep -v '^\s*$' | grep -v '@' | grep -Eiv '\b[a-z0-9._-]+ at [a-z0-9.-]+\.[a-z]{2,}\b')
  echo
  echo "## $BASE/$n.html (curl exit $code)"
  echo "subject: $(echo "$text" | sed -n 1p | sed 's/^ *//')"
  echo "author:  $(echo "$text" | sed -n 6p | sed 's/^ *//')"
  echo "date:    $(grep -o '<I>[^<]*</I>' "$D/$n.html" | head -1 | sed 's/<\/*I>//g')"
  echo "body, first lines:"
  echo "$text" | sed -n '/Messages sorted by/,$p' | sed -n '6,30p' | sed 's/^/    /'
done
rm -rf "$D"
