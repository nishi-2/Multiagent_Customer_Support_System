# Escalation Policy

Policy ID: POL-ESCALATE-001

Version: 1.0

Category: Escalation

## Purpose

This policy defines when SupportCommander must stop autonomous processing and involve a human.

## Mandatory Escalation

Escalate when:

- agent confidence is below the configured threshold
- customer identity cannot be verified
- order ownership cannot be confirmed
- transaction records conflict
- multiple policies provide conflicting guidance
- fraud or abuse is suspected
- account risk is high
- account status is restricted
- required data is missing
- a requested action exceeds the autonomous approval limit

## Refund Escalation

Refunds require escalation when:

- amount exceeds 200 USD
- refund window has expired
- previous refund history is suspicious
- transaction data is inconsistent

## Replacement Escalation

Replacement requests require escalation when:

- product value exceeds 300 USD
- the replacement window has expired
- a prior replacement already exists
- account risk is medium or higher

## Cancellation Escalation

Cancellation requests require escalation when:

- the order value exceeds 500 USD
- shipment status is unclear
- account risk is medium or higher

## Policy Conflict

If two policies produce incompatible actions, the system must not choose arbitrarily.

The workflow must:

1. stop autonomous execution
2. record the conflict
3. escalate to a human reviewer