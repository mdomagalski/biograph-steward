# Saved-data reviewer mode

Start the shared server with an explicit operator flag:

```sh
python3 app.py serve --no-browser --saved-data-only
```

For the existing image, whose entrypoint is `python app.py`, append
`serve --no-browser --saved-data-only` after the image name in the container
command. Existing token, origin, path and source settings stay in the existing
environment file. The flag applies to every HTTP connection to that server,
including loopback/SSM access. Ordinary command-line scientific tools are
separate. A local server started without this flag retains its existing behavior.

This closes a verified integration gap: the reviewer gateway permits
`POST /api/question`, and the older physical-priority option can fetch live
STRING scores inside that route. The gateway's existing
[NGINX map](https://nginx.org/en/docs/http/ngx_http_map_module.html) selects by
method and URI; it does not validate the question's parsed JSON options.
The application now enforces the saved-data policy itself, before source/model
factories, while retaining the gateway's existing route restrictions.

The mode permits saved questions, graph/path and source inspection, native GO
inspection and its authorized packet download, configured Neptune inspection,
and ordinary existing GET downloads. It blocks model setup/planning, source
retrieval, live STRING priority, construction, refresh, review changes and new
decision exports with HTTP 403 and `error_code: saved_data_only`. It does not
expand the gateway's supported POST routes. Host, Origin and client-supplied
headers cannot turn the mode off; authentication and Origin checks still apply.

The separate **Native STRING physical associations** question remains available:
it uses preserved source records and makes no network request. Previously saved
physical-priority answers also reopen using their stored source packets, without
repeating retrieval. Candidate annotations remain candidates; accepted-only
answers can legitimately be empty.

A server-generated capability bootstrap hides live ranking and source/model
controls, preserves inspection and download links, disables new decision-export
creation, and omits review-edit forms. Reviewers use **Download run ZIP** for the
complete saved graph/source package; the focused answer has its separate ZIP.
This policy can save a newly derived answer, so it is not a read-only filesystem.

`GET /healthz` continues returning HTTP 200 with status/version and adds the
nonsecret boolean `saved_data_only`. Existing Docker health checks remain
compatible. Reopening a saved workspace does not change its graph, source hashes
or scientific qualifications.
