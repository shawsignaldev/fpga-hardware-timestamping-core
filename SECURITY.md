# Security Policy

## Supported Versions

Security fixes are applied to the current `0.2.x` line. Earlier versions are not maintained.

## Reporting A Vulnerability

Report suspected vulnerabilities privately to `shawsignaldev@proton.me`. Include the affected version, input or integration conditions, impact, and a minimal reproduction when available. Do not include credentials, proprietary feed data, or other sensitive material.

Please avoid public disclosure until the report has been assessed and a coordinated release can be prepared.

## Operational Considerations

- Treat CSV input as untrusted. Run analysis with ordinary user permissions and constrain input size at the calling boundary when files come from outside the organization.
- The CSV reader serializes its temporary process-wide field-limit adjustment and restores the prior value. Other code in the process should not change `csv.field_size_limit` concurrently outside this reader.
- Treat counter width, offset, drift, and reference epoch as controlled configuration. Incorrect values can systematically alter event ordering and reported latency.
- Keep report output separate from the input CSV. The CLI rejects same-path, resolved-path, and existing hard-link aliases, but callers using the Python rendering API own their file publication policy.
- Source, event, diagnostic, and calibration identifiers must be valid UTF-8 without terminal control or Unicode format characters before they reach a report or terminal.
- Validate fixed-width arithmetic and overflow bounds for the selected RTL parameters before hardware integration.
- Keep channel routing external to each `sequence_order_guard` instance so state cannot be shared accidentally between feeds.
- Do not treat reference-model reports or RTL simulation as proof of timing closure, hardware provenance, or feed authenticity.
