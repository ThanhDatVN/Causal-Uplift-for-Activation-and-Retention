# First-user planner study protocol

**Status:** prepared, not conducted. **Participants:** five people unfamiliar with this project. Use fictional demo rows only. A session takes about 10 minutes. Do not collect personal customer data.

## Before each session

Give the participant the [local release guide](PORTFOLIO_RELEASE_2026_EN.md) and open the planner at `http://127.0.0.1:8000/planner/`. Ask them to speak aloud while working. Record browser, viewport, keyboard or assistive technology used, start/end times, actions, errors, and exact words used to describe the result. Do not explain the interface until the task ends or the participant is stuck for two minutes.

## Same task for every participant

1. Load the fictional customers and tell the observer how many rows were loaded.
2. Set contact capacity to 25%, money cap to 30, and cooldown to 30 days. Preview a draft.
3. Explain one selected customer and one skipped customer using the visible reasons.
4. Set the money cap to zero and explain the new empty draft.
5. Restore the money cap, export the evidence packet, and find where the model bundle identity appears.
6. Answer: “Does the scenario value prove that contacting these people will save this amount of money?”

After the task, ask what was confusing, what would make the draft trustworthy, and whether any label sounded like a measured causal result. For one keyboard-only pass, repeat the task without a mouse. For a screen-reader pass, use an operator familiar with that reader and record focus order, labels, status announcements, error announcements, and table navigation.

## Record per session

| Field | Entry |
|---|---|
| Anonymous session ID | |
| Browser, viewport, assistive technology | |
| Task start and end times | |
| Completed all six steps within five minutes? | |
| Number of observer hints | |
| Incorrect field entry or recovery | |
| Selected and skipped explanation | |
| Exact answer about scenario value | |
| Observed confusion and proposed change | |

Acceptance for this small usability check is at least four of five completing the main task within five minutes and none describing scenario value as measured uplift or ROI. This is an engineering usability threshold, not a statistical population estimate. If an error repeats, revise the wording or flow, then rerun that failed task with new users and report both rounds. Keep the study results separate from the automated [browser smoke report](../reports/v4/portfolio_completion/BROWSER_VERIFICATION.md).
