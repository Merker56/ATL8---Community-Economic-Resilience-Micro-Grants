# Your agent goes here

This folder is empty on purpose.

We built the on-ramp: a real commercial corridor, real businesses, one fully real
business-to-business relationship, two modeled ones built on published federal rates, a
neighborhood need signal, and a validation suite that tells you plainly whether any of it is
wrong. We did not build the vehicle. The design decisions in your agent are what you are judged
on.

## What has to be true of what you build here

- **An ADK agent**, in Python.
- **At least one tool you built yourself.** A Python function tool, or one you defined in MCP
  Toolbox—either counts. The obvious candidate wraps your cascade query. The more valuable one
  holds the logic that is not a single query: deciding what counts as exposure, weighting a path,
  turning a set of paths into a funding recommendation with an amount attached. Consuming only
  prebuilt generic tools and calling that your design does not count.
- **At least one Google-managed MCP server, consumed.** Do not author your own—use BigQuery's
  built-in server or the [MCP Toolbox for Databases](https://github.com/googleapis/mcp-toolbox).
- **Deployed to Google Cloud**—Agent Runtime or Cloud Run, your choice.
- **Your required differentiator: a BigQuery property graph, genuinely traversed.** Your agent
  must run a real multi-hop `MATCH`. A single-hop query, or a `JOIN` with the word "graph" in the
  variable name, does not count—and it is the most common way a team misses the point while
  appearing to hit it.

## The thing worth remembering while you build

**A graph makes a consequence visible. It does not make the decision.**

The most connected business in your corridor is not automatically the best investment—it may
simply be the most robust one. A business three hops downstream with a weak coefficient is barely
affected by anything. And two of your three edge types are modeled by us, which should change
how much weight a recommendation carries.

An agent that ranks by centrality and funds the top of the list has rebuilt Section 2's wrong
answer with extra steps. What you do *after* the traversal—deciding what exposure means,
what the money actually changes, and what you are assuming—is where this becomes useful instead
of merely clever.

See Section 13 of the notebook for the DDL shape and the seven traps.
