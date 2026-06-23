from flask import request

from admin.app_admin import app


_FAVICON_LINKS = (
    '<link rel="icon" href="/static/favicon.svg?v=20260624" type="image/svg+xml">\n'
    '  <link rel="shortcut icon" href="/favicon.ico?v=20260624" type="image/svg+xml">\n'
    '  <link rel="apple-touch-icon" href="/static/favicon.svg?v=20260624">\n'
    '  <meta name="theme-color" content="#101827">'
)


@app.get("/favicon.ico")
def favicon_ico():
    response = app.send_static_file("favicon.svg")
    response.headers["Content-Type"] = "image/svg+xml"
    response.headers.setdefault("Cache-Control", "public, max-age=3600")
    return response


# admin.app_admin registers an empty favicon route first; point that endpoint at the v5 logo handler.
app.view_functions["favicon"] = favicon_ico


@app.after_request
def _inject_brand_icon_links(response):
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type or request.path.startswith("/api"):
        return response
    try:
        html = response.get_data(as_text=True)
    except Exception:
        return response
    if "/static/favicon.svg" in html or "</head>" not in html:
        return response
    html = html.replace("</head>", f"  {_FAVICON_LINKS}\n</head>")
    response.set_data(html)
    response.headers["Content-Length"] = str(len(response.get_data()))
    return response

