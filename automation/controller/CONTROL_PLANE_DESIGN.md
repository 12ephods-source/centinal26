# Outbound worker controller

The controller side of the Android worker control plane is transport-agnostic and fail-closed.

It accepts only commissioned device registrations, emits only the closed capability set supported by the worker, signs jobs with the per-device credential, and verifies signed results before acknowledgement. It does not provide arbitrary remote shell execution.

Canonical flow:

1. physical commissioning establishes device identity, source commit, boot identity, and enrollment digest;
2. controller registers the device with the corresponding per-device credential fingerprint;
3. controller enqueues a bounded capability invocation;
4. Android worker polls over outbound HTTPS and validates target, scope, source commit, expiration, nonce, and HMAC;
5. worker executes only a built-in capability and returns a signed result bound to previous evidence;
6. controller verifies signature, source commit, capability, and outstanding task identity before acknowledgement.

Persistence and deployment adapters may wrap this module, but they must not weaken these invariants.
