# ENG-112: Evaluate and select an auth provider for the customer portal

**Status:** closed  
**Opened:** 2024-09-05 by `carol.white`  
**Closed:** 2024-09-12 by `carol.white`  **
**Assignee:** `alice.chen`  
**Labels:** `security`, `vendor`, `architecture`

## Problem

The customer portal currently uses custom username/password auth. The security team requires MFA and SSO support for enterprise customers by Q4 2024. We must select and contract a vendor by end of September.

## Options evaluated

| Provider | Auth protocols | Cost per MAU | Year-1 commit | Notes |
|----------|----------------|--------------|---------------|-------|
| AuthPro  | OIDC, SAML     | $0.005       | $12,000       | 99.99% SLA, transparent incident history |
| SecureID | OIDC, SAML     | $0.007       | $18,000       | Larger support team, 99.95% SLA |
| InHouse  | Custom         | $0.00        | ~$40,000 eng  | Highest control, longest timeline (6+ months) |

## Technical reasoning

- `alice.chen` reviewed the SDKs. AuthPro’s Python SDK supports async/await, which matches our FastAPI services.
- `dave.lee` confirmed AuthPro passed the Q2 vendor security review.
- `bob.martinez` raised concern about AuthPro support team size; this was mitigated because the customer portal is SaaS-only and the self-hosted connector exclusion does not apply.
- SecureID has a larger support team but a higher failure rate in the last 12 months based on their status page (99.95% SLA).

## Financial reasoning

- AuthPro is $0.005/MAU vs. SecureID’s $0.007/MAU. At 600k MAU that is $3,000/month vs. $4,200/month.
- AuthPro year-1 commit is $12k vs. SecureID $18k.
- Current SecureID contract has 3 months remaining with a $2,500 early-termination fee.
- Net savings by choosing AuthPro: $6,000 year-1 minus $2,500 termination fee = $3,500, then $1,200/month ongoing.

## Decision

Selected **AuthPro**. Migration work tracked in ENG-113.

## Links

- Slack thread: `knowledge/meetings/synthetic_auth_decision_slack.md`
- Vendor comparison: `knowledge/internal/synthetic_vendor_comparison.md`
