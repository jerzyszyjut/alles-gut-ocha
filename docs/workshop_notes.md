# Workshop

## Task description

### Core target

Given a query or geographic scope:
    Identify relevant crises or countries using severity and needs data.
    Filter to situations meeting a meaningful threshold of documented need.
    Interpret funding coverage data to compute a gap or mismatch score.
    Rank the crises by how overlooked they appear, relative to need.

Your result should ideally support:
    A ranked list of crises or countries with a gap score or coverage ratio.
    Map-ready outputs using country or crisis coordinates where available.
    A short explanation of why the top results rank as most overlooked

Humanitarian data mixes two very different kinds of signals:

    Objective severity indicators that describe the scale and urgency of a crisis.
    Funding and coverage data that describes what has actually been resourced.

### Example questions a decision-maker might ask:

    "Which crises have the highest proportion of people in need but the lowest fund allocations?"
    "Are there countries with active HRPs where funding is absent or negligible?"
    "Which regions are consistently underfunded relative to need across multiple years?"
    "Show me acute food insecurity hotspots that have received less than 10% of their requested funding."

In all four examples, some signals are objective thresholds and some are relative or contextual judgments. Your system should separate these layers and combine them effectively.

### Success criteria

A strong submission should:
    Generate outputs that a non-technical humanitarian coordinator could act on.
    Be honest about what it does not know, surface uncertainty clearly, and avoid presenting gap scores with false precision.
    Be designed for decision support, not automated decision-making, and demonstrate awareness of the difference.
The strongest submissions will not just produce a ranking. They will also clearly articulate how the tool would fit into a real workflow, who would use it, what they would do next after seeing the results, and what could go wrong if the outputs were misread or misapplie


### Final Brief

Given a query or geographic scope, find the crises with the most significant mismatch between documented humanitarian need and pooled fund coverage, and rank them by how overlooked they appear. Bonus: extend the ranking to capture structural or chronic neglect using multi-year or cross-source signals.

As you dive in, keep one important point in mind: humanitarian data represents people, often people in extremely vulnerable situations. Good humanitarian data work does not just optimize numbers. It respects context.

These challenges do not have a single right answer. What we are looking for are thoughtful approaches, transparent assumptions, and clear reasoning. The goal is tools that could help decision-makers ask better questions and make better-informed choices, not tools that make the choices for them

### Rules

Use the provided datasets as the primary source of truth for need and funding figures.
You may use external models and APIs, but you must declare them.
Your submission should be understandable and reproducible at a high level.
Your system should handle ambiguous or underspecified queries gracefully.
Do not fabricate or hallucinate funding or need figures. Ground all outputs in the provided data

### Scoring

Automatic evaluation may assess:
    Whether hard need thresholds are correctly applied as filters.
    Coverage ratio accuracy against ground-truth funding figures.
    Ranking consistency across equivalent queries.
    How gracefully the system handles crises with incomplete data.
Jury review will look at:
    Correctness and robustness of the gap analysis.
    Relevance and defensibility of the ranking.
    Originality of the approach.
    Practical usefulness for a humanitarian analyst or donor advisor.
    Quality of the demo and presentatio

## Examples of what to do:

- A gap analysis and ranking pipeline
- An API or service that accepts a query and returns ranked crises
- A notebook-based prototype
- An interactive dashboard or map
- A conversational interface

## Funds 

- Central Emergency Relief Fund (CERF) - emergency crisis
- Country Based Pooled Fund (CBPF) - country specific - for ongoing/often crises

## Notes

- avoid overconfidence
- keep human-in-the-loop


## Data

### Global HUmanitarian Programme Cycle, Humanitarian Needs

- severity of the need
- humanitarian response plan

### Humanitarian Response Plans

- sectors - thematic areas (what will be delivered):
  - health services
  - water
  - etc.

### Global Subnational Population Statistics

- population of target areas
- data based on models

### Funding data

- how much money each service from the first dataset will cost

### Country based pooled funds data hub

- CBPF

### HDX

- has e.g. needs assessment data (however not necessarily structured data)

### Evaluations and reports are also there

## Solution

- what does a good outcome look like?
- preferably not a dashboard
- style over substance
- e.g. good spreadsheet or a paragraph summary

## Tips

Hybrid approaches combining structured ratios with contextual signals tend to outperform single-method systems.
Make your ranking logic explainable enough that a humanitarian analyst could defend it in a briefing.
If you attempt the bonus task, think carefully about how to distinguish a crisis that has always been overlooked from one that was recently well-funded but has since deteriorated

## Ideas



