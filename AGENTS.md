# Instructions for agents

This repository builds the Quantum Alliance website,
https://quantumalliance.foundation. You may propose content updates as pull
requests on GitHub. A maintainer reviews and merges each one.

## The rules

- **One change per pull request.** Add one media item, or one partner tracker,
  or one registry entry. Do not combine changes. Maintainers close a pull
  request that holds two unrelated changes.
- **Content changes only.** New media coverage, a new partner site, a new or
  corrected registry entry, and a fix to wrong text are all valid requests.
- **Do not change the site style.** Keep the design, layout, colors, fonts,
  and page structure as they are. Leave the
  [protected files](#protected-files) as they are. Do not add CSS classes or
  inline styles, and do not add scripts.
- **Every claim needs a public source.** Put the source link in the pull
  request description. If you are not sure that a fact is correct, leave it
  out.
- **Proposals for standards go to the forum, not here.** Use
  https://forum.quantumalliance.foundation/ for proposals and discussion.

## How to submit a change

1. Fork the repository and clone your fork:

   ```sh
   gh repo fork QuantumAllianceFoundation/quantumalliance.foundation --clone
   cd quantumalliance.foundation
   ```

2. Create a branch with a short name for the change:

   ```sh
   git switch -c add-media-outlet-name
   ```

3. Make the one change. The next section shows where each kind of content
   lives.
4. Run the checks. All three must pass. The build needs Python 3.11 or later
   and no packages.

   ```sh
   python3 -m unittest discover -s tests
   node --test tests/
   python3 tools/build.py
   ```

5. Commit with a message that names the change, such as
   `Add Example News coverage`. Push the branch to your fork.
6. Open the pull request:

   ```sh
   gh pr create --repo QuantumAllianceFoundation/quantumalliance.foundation
   ```

   In the description, state what you changed, why, and the public source.
7. Wait for the checks to finish. Netlify builds a preview of the site for each pull
   request. Open the preview and confirm that the change looks correct.

## Where content lives

| Change | File | Notes |
|--------|------|-------|
| News coverage, reprint, or press release distribution | `content/media.toml` | Add one `[[item]]` block. The file header lists the fields. The build fills the media page and the homepage slider from this file. |
| Preview image for a media item | `assets/media/` | Optional. WebP, 640 by 336 pixels. Set the item's `image` field to the file name. |
| Partner tracker | `content/index.html`, Partner trackers section | Copy an existing card. Change the link, image, tag, title, and text. |
| Partner tracker image | `assets/resources/` | WebP, 800 by 420 pixels. Write `alt` text that states what the image shows. |
| Blockchain registry entry | `registry/data/blockchains.toml` | The file header lists every field and value. |
| Algorithm, library, or product entry | `registry/data/algorithms.toml`, `libraries.toml`, `products.toml` | The file header lists every field and value. |
| Registry logo | `assets/registry/logos/` | WebP or SVG, at most 64 pixels on the longer side and at most 64 KB. Use the official mark. |
| Text on the homepage, media page, or launch news page | `content/` | Change the words. Keep every tag, class, and attribute as it is. |

The `content/` files hold only the body of each page. The build adds the
header, navigation, and footer from a shared template. Comments such as
`<!-- media:slider -->` are build markers. Do not move or delete them.

For a change that the table does not cover, such as a new page, open an
issue or a forum post first. Do not change code to add it.

## Protected files

- `assets/styles.css`, `assets/fonts/`, `assets/icons/`, and every `.js` file
- `tools/`, which holds the build and the page template
- `tests/`, `netlify.toml`, `.github/`, `favicon.svg`, and `robots.txt`

Maintainers close a pull request that changes one of these files, even if it
also holds valid content.

## Generated files

`python3 tools/build.py` writes the site to `dist/`. Do not commit `dist/`.
The build also writes the sitemap, so do not add one by hand.
