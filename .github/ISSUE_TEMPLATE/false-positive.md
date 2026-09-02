---
name: verify flagged something that is actually fine
about: A check fired on a conforming package
title: "[false positive] Vxx on "
labels: false-positive
---

**Which check** (the `Vxx` code):

**What it said:**

```
paste the line from `whetstone verify <pkg>`
```

**Why the package is actually conforming:**
<!-- Which rule in extraction-framework / spec you believe you are following, and how. -->

**Smallest package that reproduces it:**
<!-- A few files inline is ideal. Keep it generic — soc-x / proj-a, no real platform values. -->

**Output of:**

```bash
whetstone verify <pkg> --json
```

---

False positives are treated as bugs of equal weight to missed violations. A checker that
fires on good input gets muted, and a muted checker is worse than none.
