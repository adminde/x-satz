# 0001. Record architecture decisions

Date: 2026-11-07

## Status

Accepted

## Context

X-Satz is built in phases (full score, parts, MIDIs, playing aids, integration), largely with
coding agents. Agents start every session without memory and only know what the repository
tells them. People in the club change, and whoever works on a later phase may not have been
around in phase 1.

A rule without a reason is either followed blindly or broken at the first inconvenience.
Rules in `AGENTS.md` are short by design and leave no room for their reasons or for the
options that were rejected.

## Decision

We will record every architecture decision as a file of its own in `docs/adr/`, following the
template `0000-template.md` (context, decision, consequences after Michael Nygard), numbered
with four digits. `docs/adr/README.md` describes the process and keeps the index.

We will not rewrite accepted records but supersede them with new ones. Agents only add records
with the status "Proposed". Only the maintainer accepts them.

`AGENTS.md` stays the short, action oriented guide and links to the records.

## Consequences

The reason behind every fundamental rule can be read up, and agents can see before a deviation
that they touch a decision. The history shows how the project evolved.

Every fundamental decision costs a file and a line in the index. The index is maintained by
hand. There is deliberately no check yet that every record is listed. With many records, a
small test pays off.
