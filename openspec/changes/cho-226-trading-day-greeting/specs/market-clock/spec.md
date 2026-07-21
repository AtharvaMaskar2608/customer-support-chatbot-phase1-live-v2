# market-clock

## ADDED Requirements

### Requirement: All time reasoning happens in IST
Every date and time the backend derives for customer-facing or model-facing purposes SHALL be computed in `Asia/Kolkata` from an explicitly named zone, never inherited from the host or container timezone. Storage timestamps remain UTC; this requirement covers the "what day and time is it for this customer" question only.

#### Scenario: Container timezone does not affect the answer
- **WHEN** the process runs under `TZ=UTC`
- **THEN** the clock reports the same IST date and time it would report under `TZ=Asia/Kolkata`

### Requirement: The calendar models trading sessions, not closures
The market calendar SHALL express trading days as sessions with their own windows, not as weekdays minus a holiday list. A date is a trading day when it declares a special session, or when it is a weekday that is not a holiday. This exists because special sessions fall on non-weekdays: Diwali Laxmi Pujan Muhurat trading on Sunday 8 November 2026 is a trading day that a subtraction-only rule cannot represent.

#### Scenario: Muhurat on a Sunday is a trading day
- **WHEN** the clock is asked whether Sunday 8 November 2026 is a trading day
- **THEN** it answers yes, because a special session is declared for that date

#### Scenario: Special-session windows override the default session
- **WHEN** the current moment falls inside a declared Muhurat evening window
- **THEN** the market state is the special-session state, not the ordinary post-market state

#### Scenario: Ordinary weekday holiday has no session
- **WHEN** the date is 26 January 2026, a weekday holiday
- **THEN** no session applies for the whole day

### Requirement: Session windows are half-open and ordered
Window matching SHALL use half-open intervals `[start, end)` evaluated in declared order, so boundary instants belong to exactly one window.

#### Scenario: Market close boundary is unambiguous
- **WHEN** the time is exactly 15:30:00 on a trading day
- **THEN** the state is post-market, not open

#### Scenario: Market open boundary is unambiguous
- **WHEN** the time is exactly 09:15:00 on a trading day
- **THEN** the state is open, not pre-open

### Requirement: An out-of-coverage or unavailable calendar degrades loudly
The calendar SHALL declare the date range it covers. A date outside that range, an unreadable file, or a malformed file SHALL route to weekday-only degraded mode and emit a warning. It MUST NOT be treated as "no holidays found", because that reports every weekday as a trading day and would assert an open market on a holiday.

#### Scenario: Expired calendar does not claim an open market on a holiday
- **WHEN** a calendar covering only 2026 is asked about 26 January 2027
- **THEN** the clock reports degraded weekday-only mode and logs a warning, rather than reporting a normal trading day

#### Scenario: Missing calendar still answers
- **WHEN** the calendar file cannot be read
- **THEN** the clock answers from weekday-only logic and logs a warning; callers receive an answer rather than an exception

### Requirement: Equity segment only
The calendar SHALL represent the NSE/BSE **equity** session. Commodity-derivatives holidays and split morning/evening commodity sessions are explicitly out of scope, and dates that are commodity-only closures MUST NOT be imported as equity closures.

#### Scenario: New Year's Day is a normal equity trading day
- **WHEN** the clock is asked about 1 January 2026, which appears only in the published commodity table
- **THEN** it reports an ordinary equity trading day
