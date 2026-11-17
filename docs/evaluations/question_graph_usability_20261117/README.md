# Question graph and path exploration

The application presents a question-result overview before individual evidence
details. The saved workspace remains separately accessible through its bounded
graph browser and complete source tables.

The native KRAS question returns 14 partners: 15 entities and 14 cited
connections. **Graph view** and **Show in graph** focus an individual result.
**Show all results** restores the overview. **Browse saved workspace** opens
the existing workspace browser; it does not draw all 9,724 entities at once.

**Explore paths in this saved graph** provides independent start/end searches.
Starts are eligible outgoing entities sorted with proteins first. End suggestions
respect relationship, evidence, direction, explicit symmetry and hop bounds.
The accepted-only scope explains when no locally accepted evidence is available.

Three one-hop examples in the native workspace each returned one path in the
actual browser:

| Example | Saved relationship |
|---|---|
| KRAS → CDC42BPB | Interaction annotation |
| TP53 → nucleus | Native GO location annotation |
| BRAF → ARMS-mediated activation | Pathway membership |

These paths describe recorded source context. They do not establish inferred
mechanisms or biological absence when a filtered search is empty.

**Results & evaluation** introduces source qualification, reference-label
recovery and separate prediction studies for a first-time reader. It describes
the product and evidence rather than software development history.

The UI check suite passed 176 tests. After final search-field styling and text
polish, the 53 directly affected tests passed, including empty-result navigation. Actual Chrome checks
covered the overview/detail controls, workspace browsing, typed entity filters,
all three positive path examples and the empty accepted-only explanation.

Scientific inputs, graph decisions, agent results and evaluation measurements
are unchanged. No inference or fresh source retrieval was performed.

The complete local-copy archive preserves all 213 original source, question and
agent files, with the updated committed application. Earlier actual local review
and the managed-Chrome binary-download restriction remain separately recorded
in the [editable-copy evidence](../editable_demo_copy_20261117/README.md).
That browser restriction was neither retried nor bypassed for this update.

Verification records: [hosted acceptance](hosted_acceptance.json),
[actual public browser](browser.json), [local browser and runtime bridge](local_browser.json),
[UI checks](checks.json), [complete local-copy package](package.json),
[portable software](software.json) and [documentation audit](documentation.json).
