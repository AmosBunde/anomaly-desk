"""The API service and the operator queue endpoints.

Captures every operator disposition (accept, edit, override) at field granularity, so an
override of severity is distinguishable from an override of the action list. Those
dispositions are the second scoreboard and are labeled signal; they reach the labeled set
only through a reviewed pull request, never automatically, because an automatic loop would
let the system grade its own homework.

Implemented by A29 (queue API) and A31 (override-rate capture).
"""
