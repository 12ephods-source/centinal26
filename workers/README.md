# Workers

Workers consume durable jobs and execute named capabilities under explicit policy.

Canonical worker requirements:

1. authenticate to the control plane;
2. claim a job with a lease;
3. reject unknown capabilities and invalid arguments;
4. scrub or constrain execution environment;
5. enforce timeout/resource boundaries;
6. capture stdout/stderr/result metadata as appropriate;
7. verify declared postconditions;
8. hash relevant inputs/outputs;
9. append audit evidence;
10. update durable job state.

A worker is not a general remote shell.
