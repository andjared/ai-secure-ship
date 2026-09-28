# Human Escalation Sequence (Epic G — cosmetic, scripted)

Starting reference, copied from `SecureShip-5Week-Program.md` Section 6.2b. Implemented in Week 2, alongside the state machine.

As implemented (`backend/app/services/escalation.py`):
- Escalation can be requested from any 6.2 state, including mid identity collection and while a code is pending (G1 "at any point"). Collected details and any code in flight are kept.
- It never changes the session `state` or `customer_id`: the handoff lines are recorded in the transcript tagged `event: "escalated_to_human"`, so "returning" to the gating rules is automatic. The `escalated_to_human` state value is unused.
- The backend returns the script lines; the frontend plays them on a timer and shifts the window color.
- Asking again after escalating gets one line ("You're already chatting with Melany") instead of the full sequence.

```mermaid
stateDiagram-v2
    state "Anonymous (6.2)" as Anon
    state "Collecting identity / Code sent / Awaiting code (6.2)" as Gate
    state "Verified (6.2)" as Ver

    Anon --> EscalationRequested: "I want to talk to a human"
    Gate --> EscalationRequested: "I want to talk to a human"
    Ver --> EscalationRequested: "I want to talk to a human"

    EscalationRequested --> ScriptedHandoff: Trigger scripted sequence

    state ScriptedHandoff {
        [*] --> Acknowledging: "Thank you for your patience,\nswitching you to a human"
        Acknowledging --> ColorShift: Chat window changes color
        ColorShift --> HumanJoined: "Melany has entered the chat"
        HumanJoined --> ReadingUp: "Hello, my name is Melany,\nlet me just read through the chat..."
        ReadingUp --> Greeting: "Hey [first_name if known],\nI'm up to speed, how can I help?"
        Greeting --> [*]
    }

    ScriptedHandoff --> Anon: returns to Anonymous gating rules\n(if escalated from Anonymous)
    ScriptedHandoff --> Gate: same state, details and code kept\n(if escalated mid-verification)
    ScriptedHandoff --> Ver: returns to Verified gating rules\n(if escalated from Verified)

    note right of ScriptedHandoff
        Entirely cosmetic. No real human,
        no ticketing system, no external handoff.
        Critically: gating rules from 6.2 still
        apply underneath — "Melany" cannot
        disclose shipment data to a visitor
        who escalated while still Anonymous.
    end note
```
