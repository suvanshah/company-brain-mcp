"""Custom Streamlit file uploader with a logo button (CCv2 inline)."""

from typing import Any, Dict, Optional

import streamlit as st

_HTML = """
<style>
  .logo-uploader {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    border: 1px solid #d1d5db;
    border-radius: 0.5rem;
    background: #f9fafb;
    color: #111827;
    font-size: 14px;
    cursor: pointer;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  .logo-uploader:hover {
    background: #f3f4f6;
    border-color: #9ca3af;
  }
  .logo-uploader img {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
  }
  .logo-uploader input {
    display: none;
  }
</style>
<label class="logo-uploader">
  <img class="logo-img" src="" alt="" />
  <span class="logo-text"></span>
  <input class="logo-input" type="file" />
</label>
"""

_JS = """
const _initialized = new WeakMap()

export default function (component) {
  const { data, parentElement, setStateValue } = component

  const logos = {
    slack: "https://www.google.com/s2/favicons?domain=slack.com&sz=64",
    github: "https://www.google.com/s2/favicons?domain=github.com&sz=64",
    file: "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxOCIgaGVpZ2h0PSIxOCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM2NjYiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMTQgMkg2YTIgMiAwIDAgMC0yIDJ2MTZhMiAyIDAgMCAwIDIgMmgxMmEyIDIgMCAwIDAgMi0yVjh6Ij48L3BhdGg+PHBvbHlsaW5lIHBvaW50cz0iMTQgMiAxNCA4IDIwIDgiPjwvcG9seWxpbmU+PC9zdmc+",
  }

  const img = parentElement.querySelector(".logo-img")
  const text = parentElement.querySelector(".logo-text")
  const input = parentElement.querySelector(".logo-input")

  if (img && text && input) {
    const service = data?.service || "file"
    const accept = data?.accept || ""
    const label = data?.label || "Upload"
    const multiple = !!data?.multiple

    img.src = logos[service] || logos.file
    img.alt = service
    img.style.display = "inline"
    text.textContent = label
    input.setAttribute("accept", accept)
    input.multiple = multiple

    if (!_initialized.has(parentElement)) {
      _initialized.set(parentElement, true)
      input.addEventListener("change", async (e) => {
        const files = e.target.files
        if (!files || files.length === 0) {
          setStateValue("files", [])
          return
        }
        const out = []
        for (const file of files) {
          const buffer = await file.arrayBuffer()
          const bytes = Array.from(new Uint8Array(buffer))
          out.push({ name: file.name, type: file.type, bytes: bytes })
        }
        setStateValue("files", out)
      })
    }
  }
}
"""

_LOGO_UPLOADER = st.components.v2.component(
    "logo_uploader",
    html=_HTML,
    js=_JS,
)


def logo_uploader(
    service: str,
    accept: str = "",
    label: str = "",
    multiple: bool = False,
    key: str = "",
) -> list[Dict[str, Any]]:
    """Return a list of file dicts {name, type, bytes} when the user selects files.

    `service` selects the logo: "slack", "github", or any other string.
    `accept` is the HTML accept attribute, e.g. ".zip".
    `label` overrides the button text.
    `multiple` allows selecting more than one file.
    """
    result = _LOGO_UPLOADER(
        data={"service": service, "accept": accept, "label": label, "multiple": multiple},
        key=key,
        default={"files": []},
        on_files_change=lambda: None,
    )
    return result.files if result is not None else []
