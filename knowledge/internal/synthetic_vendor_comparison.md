# Vendor comparison: Auth providers

**Date:** 2024-09-10  
**Owner:** `alice.chen`  
**Reviewed by:** `dave.lee`, `bob.martinez`

## Providers

### AuthPro

- **Cost:** $0.005 per MAU; $12,000 year-1 commit.
- **SLA:** 99.99% uptime. Excludes self-hosted connectors.
- **Security:** Passed Q2 vendor security review. SOC 2 Type II.
- **Support:** Email + chat, weekday business hours, average 2h first response.
- **SDKs:** Python, JS, Go. Python SDK supports async.

### SecureID

- **Cost:** $0.007 per MAU; $18,000 year-1 commit.
- **SLA:** 99.95% uptime.
- **Security:** SOC 2 Type II, ISO 27001.
- **Support:** 24/7 phone + chat, larger team.
- **SDKs:** Python, JS, Java. Python SDK is synchronous only.

### InHouse

- **Cost:** $0 variable cost, ~$40,000 engineering investment.
- **SLA:** Determined by our own infrastructure (currently 99.9%).
- **Security:** Full control, but requires own MFA/SSO implementation.
- **Timeline:** 6+ months.

## Are the reasons still valid?

- AuthPro’s pricing and SLA are current as of 2024-09-10. We expect a quarterly re-evaluation.
- SecureID pricing may change at renewal; the cost comparison is valid for the current contract term only.
- In-house remains an option but is not viable for the Q4 customer portal deadline.
