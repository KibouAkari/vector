# Product screenshots

Only **two screenshots are needed** for the first README gallery:

1. **`login.png`** — the actual black-hole login. Capture it without entering credentials, ideally 1600×900 or similar 16:9 framing.
2. **`workspace.png`** — dashboard or chat with a harmless demo conversation. Hide usernames, personal/project names, customer data and financial details.

Optional later: `models.png` (with credentials and account details concealed).

## Add them in under five minutes

Open the private GitHub repository, navigate to `docs/screenshots/`, choose **Add file → Upload files**, and upload the two PNGs. Check the preview before committing.

Then add this HTML between `SCREENSHOT_GALLERY_START` and `SCREENSHOT_GALLERY_END` in the root `README.md`:

```html
<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/login.png" alt="Vector cinematic login" /></td>
    <td width="50%"><img src="docs/screenshots/workspace.png" alt="Vector workspace" /></td>
  </tr>
</table>
```

Never include API keys, login tokens, host addresses, real customers, private chat messages or server logs. Keep screenshots genuine rather than generated UI mockups.
