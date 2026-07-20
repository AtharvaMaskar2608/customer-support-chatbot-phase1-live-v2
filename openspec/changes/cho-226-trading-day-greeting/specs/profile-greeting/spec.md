# profile-greeting

## ADDED Requirements

### Requirement: Greeting is selected from the market clock
`GET /api/greeting` SHALL return a greeting key and its template alongside the first name. The key is selected by walking the configured windows in order against the current IST moment: 06:00–09:00 `MORNING` on any day, 09:15–15:30 `MARKET` and 15:30–23:00 `POST_MARKET` on trading days only, a declared special session window `MUHURAT`, and `DEFAULT` when nothing matches.

#### Scenario: Market hours on a trading day
- **WHEN** a customer opens the widget at 11:00 IST on an ordinary Wednesday
- **THEN** the endpoint returns the `MARKET` key and its template

#### Scenario: Market hours on a holiday
- **WHEN** a customer opens the widget at 11:00 IST on 26 January 2026
- **THEN** the endpoint returns `DEFAULT`, because market windows require a trading day

#### Scenario: Morning applies on non-trading days
- **WHEN** a customer opens the widget at 07:00 IST on a Sunday
- **THEN** the endpoint returns `MORNING`, which asserts nothing about the market

#### Scenario: Unmatched windows fall back
- **WHEN** the time is 09:05 IST (pre-open) or 02:00 IST (overnight)
- **THEN** the endpoint returns `DEFAULT`

### Requirement: Templates carry a placeholder so the name keeps its styling
The endpoint SHALL return the template text containing a `{clientRef}` placeholder rather than a fully rendered greeting, so the client can render the customer's name with its own styling. `{clientRef}` is the **first name** already derived from the profile. When no first name is available the endpoint SHALL return a fallback template that contains no placeholder.

#### Scenario: Name keeps its accent styling
- **WHEN** the client renders a template containing `{clientRef}`
- **THEN** the first name appears in the accent colour within the headline, as it does today

#### Scenario: No first name available
- **WHEN** the profile yields no usable first name
- **THEN** the endpoint returns a fallback template with no placeholder, and the rendered headline contains no double space or dangling punctuation

### Requirement: Greeting selection never blocks or breaks the screen
Any failure in clock, calendar, or template lookup SHALL degrade to the `DEFAULT` key. Greeting selection MUST NOT cause the endpoint to fail, and a client that receives no key or template SHALL render the existing static greeting.

#### Scenario: Calendar unavailable
- **WHEN** the market calendar cannot be read
- **THEN** the endpoint still returns 200 with the `DEFAULT` key

#### Scenario: Client receives a partial payload
- **WHEN** the response omits `greetingKey` or `template`
- **THEN** the home screen renders the current static greeting rather than an empty headline

### Requirement: Greeting is presentation-only and stable once painted
The greeting SHALL be rendered as the entry-screen headline only. It MUST NOT be inserted as a chat message, stored in conversation history, or routed through intent handling. Once painted it SHALL NOT change while the screen remains open, even if a window boundary passes. It is recomputed on a fresh entry screen, including after Restart.

#### Scenario: Boundary passes while the screen is open
- **WHEN** the customer has the entry screen open at 15:29 IST and the clock passes 15:30
- **THEN** the painted greeting does not change

#### Scenario: Restart recomputes
- **WHEN** the customer taps Restart
- **THEN** the entry screen re-renders and the greeting is selected again for the current moment

#### Scenario: Greeting never enters the conversation
- **WHEN** any greeting key is selected
- **THEN** no chat message is created and the agent's thread is unaffected

### Requirement: Greeting key is logged without PII
The selected key and timestamp SHALL be recorded on the session record. The customer's name MUST NOT be logged.

#### Scenario: Log line carries the key only
- **WHEN** a greeting is selected
- **THEN** the log records the greeting key and timestamp, and contains no name or client code
