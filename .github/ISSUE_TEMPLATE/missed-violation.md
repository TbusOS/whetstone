---
name: verify let something through that it should have caught
about: A package violates a rule and the checker stayed quiet
title: "[missed] "
labels: missed-violation
---

**Which rule was violated**
<!-- Section of references/extraction-framework.md or spec/skill-package.md. Quote it. -->

**The package that should have failed:**
<!-- Smallest reproduction, generic values only (soc-x / proj-a). -->

**What `verify` reported instead:**

```
paste the output, including the summary line and exit code
```

**If you know how it slips through, say so**
<!-- The four bypasses fixed so far were all of this shape: a dropped separator, a heading
that merely mentioned "L3", a parenthesised platform suffix, a table without leading pipes.
Anything that lets a single-platform lesson reach `high` is the highest-value report here. -->
