---
name: Legal Document Intelligence
description: A filing-review ledger for evidence-led public legal research.
colors:
  carbon: "#101820"
  registry-blue: "#174a76"
  signal-red: "#a63832"
  cool-paper: "#f3f5f7"
  sheet: "#ffffff"
  ledger-line: "#cbd3dc"
  secondary-ink: "#56616d"
  placeholder-ink: "#6c7782"
  deep-signal: "#741f1b"
  quiet-blue: "#e7eef5"
typography:
  scale: ["0.62rem", "0.64rem", "0.66rem", "0.68rem", "0.7rem", "0.74rem", "0.75rem", "0.76rem", "0.78rem", "0.82rem", "0.84rem", "0.85rem", "0.86rem", "0.88rem", "0.95rem", "0.96rem", "1rem", "1.04rem", "1.05rem", "1.08rem", "1.3rem", "1.5rem", "1.62rem", "2.2rem", "2.25rem", "2.45rem", "2.55rem", "2.65rem", "3.3rem", "3.4rem", "4rem", "4.75rem"]
  display:
    fontFamily: "Arial Nova, Helvetica Neue, Arial, sans-serif"
    fontSize: "4.75rem"
    fontWeight: 700
    lineHeight: 0.95
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Arial Nova, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.1
  body:
    fontFamily: "Arial Nova, Helvetica Neue, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Arial Nova, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.04em"
rounded:
  control: "2px"
  surface: "4px"
spacing:
  unit: "8px"
  compact: "12px"
  standard: "24px"
  section: "48px"
components:
  button-primary:
    backgroundColor: "{colors.carbon}"
    textColor: "{colors.sheet}"
    rounded: "{rounded.control}"
    padding: "13px 18px"
  input:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.carbon}"
    rounded: "{rounded.control}"
    padding: "14px 16px"
---

# Design System: Legal Document Intelligence

## Overview

**Creative North Star: "The Filing Review Ledger"**

The product should feel like the working surface of a serious transaction review: ordered, dense where evidence requires density, and visibly anchored to the record. The visual system replaces generic dashboard cards and warm editorial styling with accession rails, ruled sections, document coordinates, analytical briefs, and tabular evidence rows.

The interface is an operating tool, not a marketing page. Expression comes from structure, numbering, typography, and the rhythm of a review ledger. Controls remain familiar and direct.

**Key Characteristics:**

- Analytical split views rather than centered heroes.
- Flat ruled surfaces rather than floating cards.
- Registry blue for navigation and selection; signal red only for errors and incomplete support.
- Source identity and limitations remain visible near every result.

## Colors

The palette is cool and institutional: carbon ink on cool paper, with registry blue for active work and one restrained signal red for problems.

**The Evidence Color Rule.** Accent color communicates selection, navigation, or state. It never decorates a neutral surface.

## Typography

**Display Font:** Arial Nova, with Helvetica Neue and Arial fallbacks  
**Body Font:** Arial Nova, with Helvetica Neue and Arial fallbacks  
**Data Font:** ui-monospace for identifiers, locations, and measurements only

Hierarchy comes from weight, alignment, measure, and tabular rhythm. Large type is reserved for the research thesis. Labels use compact tracking but avoid repeated all-caps eyebrow patterns.

## Layout

The desktop shell uses a 1440px maximum working width and a twelve-column grid. The research route opens as an asymmetric workbench: the question and answer own the primary field; collection status and methodology occupy a narrower register. Evidence and sources use row-based ledgers. At tablet widths, secondary registers move below the main task. At mobile widths, all ledgers become labeled vertical records with no horizontal page overflow.

## Elevation & Depth

The system is flat by default. Depth comes from nested paper tones, rule weight, sticky rails, and controlled overlap at the top of the workspace. Shadows appear only on focused or sticky controls and never combine with a border on a card-like surface.

## Shapes

Controls use 2px corners. Structural surfaces use 4px corners or square ruled edges. Pills are limited to compact status filters. Content is grouped by whitespace and horizontal rules, not rounded containers.

## Components

### Buttons

Primary actions use carbon ink with white text, 2px corners, and direct verb labels. Hover shifts to registry blue; focus uses a visible offset ring; active state moves down one pixel.

### Inputs

Fields use white paper, a ledger-line border, and a 2px corner. Focus changes the border to registry blue and adds a restrained outer ring. Error states use signal red with a recovery instruction.

### Navigation

The header behaves like an accession register: compact brand block, current collection state, and ruled text destinations. The active route uses registry blue and a bottom rule rather than a filled pill.

### Evidence ledger

Each result begins with a stable source number and location, then document identity, passage, relevance, and the canonical source action. Rows can expand in height but retain the same information order.

## Do's and Don'ts

### Do:

- **Do** make the research task and source record visible in the first viewport.
- **Do** use tabular figures for counts, scores, and source coordinates.
- **Do** preserve 44px touch targets and visible keyboard focus.
- **Do** explain empty, loading, incomplete, and error states in place.

### Don't:

- **Don't** use pastel metric tiles, floating card grids, decorative gradients, or glass effects.
- **Don't** turn evidence metrics into legal-correctness claims.
- **Don't** use serif display type as shorthand for legal professionalism.
- **Don't** hide source identity or limitations behind secondary navigation.
