# answer-feedback (delta)

## ADDED Requirements

### Requirement: Inline rating chip on completed answers
Every answer-carrying message — report file card, email confirmation, data card, and the final agent text bubble of an exchange — SHALL render a small inline 👍/👎 chip beneath it. Tapping a thumb SHALL set that rating (visually selected immediately, optimistically); tapping the other thumb SHALL switch the rating; tapping the selected thumb SHALL do nothing. Chips SHALL remain available on older answers (scrollback stays ratable), SHALL never interrupt or overlay the conversation, and SHALL NOT appear on clarifying questions, progress indicators, sticker rows, or mid-stream partial text. Down-vote reasons, free-text comments, and un-rating are out of scope.

#### Scenario: Rating a KB answer
- **WHEN** the agent's answer finishes streaming and the user taps 👍 under it
- **THEN** the thumb renders selected immediately and the rating is submitted in the background

#### Scenario: Switching a rating
- **WHEN** the user taps 👎 on an answer they previously rated 👍
- **THEN** the chip shows 👎 selected and the stored rating for that exchange becomes `down`

#### Scenario: No chip on non-answers
- **WHEN** the agent asks a clarifying question or a progress pill is showing
- **THEN** no feedback chip renders

### Requirement: Feedback submission endpoint
The backend SHALL expose `POST /api/feedback`, authenticated by the same headers as `/api/chat` (missing credentials → HTTP 400 `MISSING_CREDENTIALS`). The body SHALL carry `rating` (`up` | `down`), optional `anchorSeq`, and `source`; invalid values → HTTP 400. On success the rating SHALL be recorded against the session's thread — anchored to `anchorSeq` when provided, else to the thread's latest turn — and the endpoint SHALL respond `{"ok": true}` without ever calling the model. Submission failures SHALL be silent on the frontend: a lost rating never surfaces an error.

#### Scenario: Agent-path rating is precisely anchored
- **WHEN** the shell submits a rating with the `anchorSeq` from the exchange's `done` event
- **THEN** the stored row references exactly that turn seq

#### Scenario: Sticker-path rating anchors server-side
- **WHEN** a rating arrives without `anchorSeq` right after a guided-flow report completes
- **THEN** the rating anchors to the thread's latest turn (the flow-event memo of that completion)

#### Scenario: Missing credentials
- **WHEN** `/api/feedback` is called without the auth headers
- **THEN** the response is HTTP 400 `{"error": "MISSING_CREDENTIALS"}` and nothing is stored
