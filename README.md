# Driverless Map

Where autonomous ride-hailing actually carries passengers, across operators,
with a source for every claim.

**Live:** https://driverlessmap.com

One Python file on the standard library. No framework, no database, no disk, no
dependencies.

## Run it

```powershell
python server.py
```

Then open http://127.0.0.1:8090.

Environment: `HOST` (default 127.0.0.1), `PORT` (8090), `SITE_URL` (canonical
origin used for links, canonicals and the sitemap).

## Why this exists

Coverage of this industry is written per company, because companies are what
people follow. That makes the obvious question hard to answer: *where can I
actually get one of these, and who runs it?* This answers it across operators.

## The two conventions that matter

**Every row carries a named source.** A test enforces it, because a single
unsourced figure would undermine a page whose only value is being trustworthy.
Where sources disagree, the range is printed rather than a tidy average. Where a
figure cannot be sourced, it is left out and the gap is stated instead.

**"Driverless" means no safety monitor aboard.** Services that still run with one
are listed in their own table and never counted in the main one. Merging the two
is the most common way coverage of this industry misleads people, and there is a
test asserting it does not happen here.

## Structure

- `server.py` — the whole application, including the data tables
- `test_site.py` — tests; most of what can break here is data, not code
- `style.css` — styling, design tokens at the top
- `render.yaml` — Render blueprint

## Updating the data

Everything lives in the tables at the top of `server.py`. Edit the rows, bump
`_UPDATED`, and push. That is the entire maintenance loop.

`_UPDATED` is one value rendered in two formats, so the date shown to readers and
the date in the sitemap cannot drift apart.

## Deployment

Render, Python 3.13.9, Starter instance, no disk. There is no user-generated
content and therefore no mutable state, which is what makes this simpler than a
forum: deploys are zero-downtime and there is no single-instance ceiling.

```powershell
python -m unittest test_site.py -v
```

## Not affiliated

Independent. Not affiliated with, endorsed by or sponsored by Waymo, Zoox,
Tesla, Uber or any other operator. Waymo, Zoox, Tesla, Cybercab, Robotaxi and
Full Self-Driving are trademarks of their respective owners.
