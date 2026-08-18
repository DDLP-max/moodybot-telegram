# Canonical Suite

**Inspector principle — not a pipeline layer.**

## Asymmetric regression protection

Most teams protect against bugs.

Moody also protects against losing great writing.

| | Hall of Fame | Canonical |
|---|---|---|
| Size | Growing — thousands of starred sentences | Small — maybe 30–50 responses |
| Purpose | Training signal | Regression suite / identity |
| Change rate | High | Slow, hand-picked |
| Question | Would someone steal this sentence? | If Moody couldn't write these anymore, has something fundamental broken? |

Canonical is **not** identical wording enforcement.
It is a **quality floor**.

## Never-regress examples (seed set)

| ID | Lens | Type | Floor line |
|---|---|---|---|
| Foreplay | Pattern Recognition | Language | The word "foreplay" already decided the hierarchy. / It ranked it. |
| Prison | Bourdain | Craft | That's like saying a prison cell is just a room. |
| McDonald's | Bourdain | Craft | McDonald's doesn't make the best burger. It makes the safest one. |
| Breaking Bad | Bourdain | Craft | …raised the price of impressing you. |
| Cat Lady | Emotional Intelligence | Projection | Every threat is autobiographical. |
| Different Things | Emotional Intelligence | Exit | Most people don't edit the relationship. They edit the ending. |

## Run after significant craft changes

```bash
python -m inspector canonical
python -m tests.test_canonical_suite
```

Expected:

```
PASS
✓ Foreplay
✓ Prison
✓ McDonald's
✓ Cat Lady
✓ Breaking Bad
✓ Different Things
```

## Product maturity

Until Canonical exists, every conversation is "here's another failure."

With Canonical: "This one is Moody. Never lose it."

That's how products mature — not by endlessly fixing weaknesses, but by identifying strengths and making them impossible to accidentally erase.
