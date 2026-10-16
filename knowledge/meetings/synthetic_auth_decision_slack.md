# Slack discussion: Auth provider decision

**Date:** 2024-09-12  
**Channel:** #eng-architecture  
**Participants:** `alice.chen`, `bob.martinez`, `carol.white`, `dave.lee`  

## Original ticket

Ticket: ENG-112 "Evaluate and select an auth provider for the customer portal"
Opened: 2024-09-05 by `carol.white`

## Messages

**alice.chen:**
> I’ve reviewed the three short-listed auth providers. My recommendation is **AuthPro**.
> Technical reasons:
> - Supports OIDC and SAML out of the box.
> - Provides a Python SDK with async support, which aligns with our FastAPI backend.
> - SLA is 99.99% with incident history that’s transparent.
> Financial reasons:
> - $0.005 per MAU, which is 30% cheaper than SecureID at $0.007 per MAU.
> - Year 1 commitment is $12k vs. SecureID’s $18k.

**bob.martinez:**
> Concerned about AuthPro’s smaller support team. If we hit an edge case, response time could lag.
> Are we confident the 99.99% SLA actually covers our use case? Their SLA excludes self-hosted connectors.

**carol.white:**
> Good catch. The customer portal is SaaS-only, so self-hosted connector exclusion is irrelevant.
> I updated the ticket with this reasoning.
> We need a decision by Friday or the Q4 launch slips.

**dave.lee:**
> From a security audit perspective, AuthPro passed our vendor review last quarter.
> I’d also note that switching away from SecureID would save us ~$6k/year, but we have a 12-month contract with SecureID that has 3 months left.
> Breaking the contract costs a $2.5k early-termination fee.

**alice.chen:**
> Net effect: AuthPro still saves money even with the termination fee by month 8.
> I propose we approve AuthPro now and start the migration in two sprints.

**carol.white:**
> Approved by PM. I’ll create the migration ticket and close ENG-112.
> Decision owner: `alice.chen` (technical), `carol.white` (product).
