from flask import request

from admin.app_admin import app


_FAVICON_LINKS = (
    '<link rel="icon" href="/static/logo.svg" type="image/svg+xml">\n'
    '  <link rel="shortcut icon" href="/favicon.ico" type="image/svg+xml">\n'
    '  <link rel="apple-touch-icon" href="/static/logo.svg">\n'
    '  <meta name="theme-color" content="#101827">'
)


@app.get("/favicon.ico")
def favicon_ico():
    response = app.send_static_file("logo.svg")
    response.headers["Content-Type"] = "image/svg+xml"
    response.headers.setdefault("Cache-Control", "public, max-age=3600")
    return response


@app.after_request
def _inject_brand_icon_links(response):
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type or request.path.startswith("/api"):
        return response
    try:
        html = response.get_data(as_text=True)
    except Exception:
        return response
    if "/static/logo.svg" in html or "</head>" not in html:
        return response
    html = html.replace("</head>", f"  {_FAVICON_LINKS}\n</head>")
    response.set_data(html)
    response.headers["Content-Length"] = str(len(response.get_data()))
    return response
