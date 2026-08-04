# Personalised Textbook Generation — Product Proposal
**Version:** 1.0  
**Status:** Pre-build. Concept validated through structured evaluation.  
**Date:** March 2026  
**Classification:** Standalone product + community layer

---

## Executive Summary

A teacher-facing AI generation tool that produces personalised, printable textbook booklets for differentiated learner groups within a classroom. The teacher is the driver. The student never touches the software. The output is a physical artifact — printed, written in, taken home — designed for serious independent reading at the right level for each learner.

A community layer allows teachers to share the configurations that produced their best booklets, building a collective knowledge base of what works across subjects, grade levels, and learner profiles.

**Overall rating: 7.2 / 10.** Strong concept, execution-dependent, right market timing. Build-worthy.

---

## Part 1 — The Problem

### What Teachers Are Dealing With

Differentiated instruction is one of the most consistently cited challenges in K-12 teaching. Teachers know they should pitch material at different levels for different learners. Most are not doing it adequately because producing differentiated materials manually is time-consuming, and the tools that exist to help are either screen-based, student-facing, or adaptive in ways that remove teacher judgment from the process.

The result is the lowest-denominator classroom: the teacher explains a concept at the level where struggling students can follow. Advanced students sit through an explanation they grasped in the first two minutes. Below-average students get the explanation but not enough scaffolding to consolidate it independently. Everyone gets the same worksheet afterward.

This is not a failure of teacher effort. It is a failure of available tools.

### The Specific Gap

There is no tool that:
- Lets a teacher describe their learner groups in plain language
- Generates print-ready differentiated materials for each group
- Tracks concepts covered and links them across a term
- Keeps the teacher as the professional reviewing and approving output
- Requires zero screen time from students

Most edtech tries to solve differentiation by putting software in front of students. This product solves it by putting a better production tool in front of teachers.

### Why Now

Three things are converging in 2026:

**AI generation quality has crossed a threshold.** A year ago, LLM-generated educational content was visibly synthetic and teachers would immediately distrust it. Today, with the right architecture — structured output schemas, deterministic renderers, inline quality checking — the output can pass careful teacher review and be genuinely useful.

**Post-pandemic learning gaps have made differentiation more urgent.** Classrooms are more heterogeneous than they were in 2019. The spread between struggling and advanced students in the same classroom widened during remote learning and has not fully closed. Teachers are actively looking for tools that help them serve that range.

**Screen fatigue and device skepticism is growing.** The Chromebook backlash is real across K-8 and much of high school. A print-first product is entering the market at a moment when the screen-first assumption is being questioned. A tool that produces something you print, hand out, and put the device away is a genuine differentiator.

---

## Part 2 — The Product

### Core Concept

A two-week personalised booklet. The teacher generates one per learner group. Each booklet covers the same core concepts but serves them at the right level — different depth, different scaffolding, different worked examples, different practice problem calibration — for each group.

The basic learning objective is the same across all groups. The route to it is different.

### What the Teacher Does

**Setup (once per subject, once per term):**
- Connect their class roster
- Map the curriculum: which concepts, in what order, over what timeline
- Set depth parameters per concept (survey / standard / deep)
- Describe their learner groups in plain language — the teacher names them, the tool does not impose a hierarchy

Example group descriptions a teacher might write:
- *"Strong readers, confident with algebra, finished early, need extension and connections to upcoming topics"*
- *"Grade level, needs worked examples before abstract explanation, some vocabulary gaps in mathematical language"*
- *"Below grade level, needs prerequisite bridging, visual representations help, more white space for working"*

**Generation (weekly or fortnightly):**
- Select: which concepts this fortnight, which groups
- System generates one booklet per group
- Teacher previews — reads through, adjusts if needed
- Teacher approves and sends to print

**Delivery:**
- Students receive printed booklets
- They work through them in class and at home
- No devices required after printing

**Feedback (brief, after each cycle):**
- Teacher logs which concepts landed per group
- Simple interface: three concepts, thumbs up / partial / needs revisit
- Takes under two minutes — done while students pack up
- System updates group profile, next generation improves

### What the Booklet Contains

Each two-week booklet for a group includes:

**Cover page:** Student name space, subject, date range, no ability-level label visible to students.

**Concept sections (3–5 per fortnight):** Each section follows a fixed internal structure:
1. Intuition hook — the felt problem before the named solution
2. Plain explanation calibrated to group level
3. Formal definition (depth varies by group)
4. Worked example (scaffolding varies by group)
5. Diagram where needed
6. Practice problems (3 per section: warm / medium / cold, calibrated to group)
7. Write-in space sized for actual student handwriting

**Connections page:** Explicitly links new concepts to what the group has previously covered. The below-average group sees connections to foundational concepts they confirmed. The advanced group sees connections forward to upcoming material.

**Reflection page:** What did you understand well. What is still unclear. Space for the student to write. The teacher reads these and uses them to inform the next feedback log.

### The Differentiation Model

The same core objective. Different routes.

| What changes per group | What stays the same |
|---|---|
| Depth of explanation | The concept being taught |
| Number of worked examples | The core learning objective |
| Scaffolding density | The two-week timeline |
| Practice problem difficulty distribution | The section structure |
| Prerequisite bridging | The formatting and design quality |
| Analogy and example choice | |
| Amount of write-in space | |

A Grade 7 student in the below-average group and a Grade 7 student in the advanced group are studying the same concept. They are not receiving the same document. They are receiving the document calibrated for their current capacity to engage with it.

### The Concept Map

The system maintains a concept map per group, updated by teacher feedback after each cycle.

```
Concept status options:
  not_started     → not yet introduced
  introduced      → covered in booklet, not yet assessed
  confirmed       → teacher marked as landed
  needs_revisit   → teacher flagged, queued for next cycle
  blocked         → prerequisite not confirmed, cannot advance
```

The concept map drives what the next booklet reinforces, what it introduces fresh, and what prerequisite bridging it includes. By term 2, the generation is noticeably more calibrated than it was in week 1 because the map has real data from real classroom observations.

### The Technical Architecture

The generation pipeline uses structured output throughout. The LLM never writes HTML. It fills typed fields — prose into body fields, math into formula fields, steps into structured step arrays. A deterministic renderer converts these into print-ready HTML with full `@media print` support.

Quality checking runs in two tiers:
- **Inline per section:** structural checks immediately after each section generates — catches empty blocks, raw LaTeX, unclosed elements, missing required fields
- **Document level:** once at the end — cross-section consistency, difficulty progression, prerequisite ordering

Failed sections rerun in isolation. Only the node that failed reruns, not the whole pipeline.

The output format is HTML rendered to PDF for printing. The design system is fixed — the teacher does not design the booklet, they configure the content. This ensures consistent quality regardless of the teacher's design skills.

---

## Part 3 — The Community Layer

### The Concept

An OpenClaw-equivalent for textbook generation. Teachers share the configurations — group descriptions, depth settings, concept sequencing, customisations — that produced their best booklets. Other teachers import those configurations, adapt them for their own class, and get a strong first generation without the trial and error the first teacher went through.

What gets shared is the recipe, not the dish. The input settings, not the generated content.

### What Sharing Looks Like

After a teacher approves a booklet they are satisfied with, the tool asks one question:
*"Would you like to share the settings that produced this booklet with the community?"*

One tap. The settings are packaged — subject, grade level, group descriptions, depth parameters, any customisations — and submitted. The teacher adds a brief note if they want. They do not write a post, fill out a form, or explain their methodology.

### What Discovery Looks Like

A teacher opens the community. They see:
- Subject filter
- Grade level filter
- Most used this month
- Highest rated by classroom outcome

They select Grade 6 Mathematics. They see the top configurations other Grade 6 math teachers have shared, rated by teachers who used them in real classrooms. They click one, read the group descriptions, see ratings and comments, import it in one click.

That is the experience. Not a feed. Not a forum. A searchable library of configurations with outcome ratings.

### The Rating System

Ratings are outcome-based, not opinion-based. Teachers rate whether the generated booklet actually worked in their classroom — did the difficulty calibration feel right, did students engage with the material, would they generate from this configuration again.

A configuration with 20 uses and a 4.8 rating is trustworthy. A configuration with 2 uses and no ratings is surfaced as unvalidated. The difference is shown clearly.

### The Subject Spine Library

The longer-term community asset: for each subject and grade level, the community collectively develops a canonical concept sequence. Grade 6 Mathematics — what are the core concepts, in what order, with what prerequisite relationships.

This is not AI-generated. It is built by teachers through use and contribution over time.

When a new teacher onboards for Grade 6 Mathematics, they import the community spine, adjust it to match their school's curriculum scope and sequence, and start generating. They do not build the concept map from scratch.

The spine gets better as more teachers use it, flag missing concepts, and suggest reordering. This is the asset that makes the platform genuinely hard to leave.

### Why the Community Changes the Score

Without the community layer: competitive moat is positional only. The generation pipeline can be replicated.

With a functioning community: the collective configurations, outcome ratings, and subject spines accumulated over two years of real classroom use cannot be replicated quickly. A competitor starting fresh cannot offer a library of 500 teacher-validated configurations across 20 subjects and 13 grade levels. That library is the moat.

The community also solves the first-run problem — the highest-friction moment in adoption. A teacher who starts from a proven configuration shared by a teacher in their subject and grade level has a much higher chance of a successful first booklet than a teacher starting from scratch.

---

## Part 4 — The Chat Mode Integration

### The Second Path

Parallel to the standalone textbook product is a chat-integrated version for individual learner sessions. The chat does not generate full textbooks. It generates sections — one at a time, triggered by the diagnostic signals from the conversation — rendered in HTML for reading rather than delivered as chat bubbles.

**The session rhythm:**
1. Chat gathers diagnostic signal (5–10 min) — implicit signals, not self-report
2. Threshold met → section generated and rendered in a side panel
3. Learner reads independently (20–30 min) — chat waits, clarify widget available
4. Learner returns → chat closes the session: short quiz, targeted corrections, concept map update

**Why sections not full textbooks in chat:**
- Faster to generate — one section at a time, lower latency
- Easier to quality-check — smaller unit, inline QC catches issues immediately
- Natural session rhythm — learner reads for 20 minutes, not 2 hours
- Progressive — each session generates the next section the learner needs, not the whole curriculum upfront

**The relationship between the two paths:**
The chat mode validates the generation quality at section level before the full periodical product is built. If generated sections demonstrably help learners understand more than equivalent chat exchanges, that is the proof of concept that justifies the full teacher-facing periodical product. Build chat sections first. Validate. Then scale to periodicals.

---

## Part 5 — Evaluations

### Dimension Scores

| Dimension | Score | Key finding |
|---|---|---|
| Problem validity | 9.0 / 10 | Real, urgent, universally acknowledged |
| Solution fit | 7.5 / 10 | Right approach, quality unvalidated at scale |
| Market size | 7.0 / 10 | Large but slow and friction-heavy |
| Timing | 8.0 / 10 | Right moment — AI quality, post-pandemic gaps, screen fatigue |
| Competitive moat | 5.5 / 10 | Positioning moat only at launch; community builds it over time |
| Execution risk | 6.0 / 10 | Three genuinely hard problems (see below) |
| Teacher adoption likelihood | 8.0 / 10 | High among experienced, differentiating teachers |
| Output quality (demonstrated) | 8.5 / 10 | Calculus section is strong; cross-subject scale unvalidated |
| **Overall** | **7.2 / 10** | Build-worthy, execution-dependent |

### What Moves the Score Up

- A validated pilot study showing measurable learning outcomes from booklet-based differentiated instruction — even two classrooms, one term — moves overall from 7.2 to 8.5
- Generation quality demonstrated consistently across 5+ diverse subjects and grade levels moves moat score from 5.5 to 7.0
- A functioning community with 50+ quality-rated configurations moves moat score from 5.5 to 7.5 and adoption from 8.0 to 8.5
- Clean sub-2-hour onboarding with strong first booklet moves adoption from 8.0 to 9.0

### What Moves the Score Down

- A content accuracy failure in a high-stakes subject discovered by a teacher after printing — one incident moves adoption likelihood from 8.0 to 5.0 among that teacher's network
- Teacher feedback loop completion below 40% breaks the concept map compounding — the product becomes a static worksheet generator
- Onboarding taking longer than 2 hours causes early adopter drop-off before first generation

### The Experienced vs Inexperienced Teacher Split

**Experienced teachers:** Already differentiating mentally, know their class, will see the value immediately. Setup is fast because they have clear answers. Will adopt quickly and become advocates. Target these first.

**Inexperienced teachers:** Still developing ability to segment and differentiate. Three simultaneous groups feels high-stakes when they are not yet confident in their own judgment. Solution: start with two groups not four. Below average and everyone else. Add groups as confidence grows. The tool should support progressive complexity, not require the full model from day one.

**Go-to-market implication:** Do not sell to inexperienced teachers first. Sell to experienced teachers who are already differentiating informally. Let their advocacy bring the tool to less experienced colleagues.

### The Three Genuinely Hard Execution Problems

**1. Generation quality consistency across subjects**
The calculus section is impressive. A Grade 4 fractions section, a Grade 8 Civil War section, and an AP Chemistry section all need to be equally good. Subject matter accuracy across the full K-12 curriculum is a hard problem. The quality checker catches structural failures. It does not reliably catch a conceptually wrong explanation of photosynthesis or a miscalibrated analogy in a history section.

**2. Teacher feedback loop completion**
The product's value compounds if teachers consistently record which concepts landed. Many will not — teachers are already overloaded with administrative tasks. The feedback interface has to take under two minutes. If it takes longer, many teachers will skip it after the first few cycles. The system must remain useful when feedback is incomplete, which means first-pass generation has to be good enough that the absence of feedback does not significantly degrade quality.

**3. The sales motion into schools**
Even with a product that teachers love, getting budget approval and navigating procurement requires a sales function that most technical teams underestimate. The most adoptable path in the short term: teacher-direct subscription that individuals can purchase without institutional approval. School and district deals follow after individual adoption proves the value.

---

## Part 6 — The Commercial Model

### Pricing Shape

**Per-teacher subscription, not per-student.** The teacher is the customer. Per-pupil licensing adds procurement friction and makes pricing conversations with administrators harder. Per-teacher pricing is clean and scales with usage.

Indicative pricing:
- Individual teacher: $25–$40/month
- School (all teachers): $800–$1,500/month depending on school size
- District: negotiated, higher volume

### The Trial That Sells Itself

A two-week free trial with real output. The teacher generates one complete fortnight's booklets for their class, prints them, uses them, sees how students respond. No demo, no sales call. A real booklet in the teacher's hand. If the output is good, it sells itself. If it is not, no amount of sales effort would have worked anyway.

### The Subscription Flywheel

```
Teacher generates first booklet
  → First booklet is good (quality bar essential)
    → Teacher uses it, sees student response
      → Teacher records outcome, shares configuration
        → Concept map improves, next booklet better
          → Teacher subscribes, tells colleagues
            → Colleague imports teacher's configuration
              → Colleague's first booklet is good
                → Cycle repeats
```

The flywheel only spins if the first booklet is good. Everything else in the commercial model is downstream of generation quality.

### The Integration Angle (Phase 2+)

School marks and student registry integration. Once a school has a roster integration, the tool becomes embedded in the school's operational workflow. Concept map data connects to grade records. Group assignments connect to existing student data. That integration makes the tool difficult to remove — it becomes infrastructure rather than a nice-to-have.

This is a Phase 2 or Phase 3 feature. Phase 1 is: teacher describes their groups, system generates booklets, teacher prints them, the output is good.

---

## Part 7 — Open Questions That Still Need to Be Thought Through

These are the questions that were raised during evaluation but not resolved. They need answers before build decisions are made in those areas.

### Product Questions

**1. How do you handle the first booklet cold start?**
The first generation has no concept map data, no prior group feedback, no community configuration to import from. It is generated entirely from the teacher's description. How good does that first generation need to be to retain the teacher? What is the minimum viable description the teacher has to provide to get a useful first output? Is there a structured onboarding interview that produces better first descriptions than a blank text field?

**2. What is the group label strategy?**
Students will see their booklet. The booklet should not have a visible ability level on it — "Group B: Below Average" is stigmatising. How do teachers label groups in a way that is meaningful to them in the tool but neutral on the printed artifact? Does the tool enforce neutral labels or leave it to the teacher?

**3. How do you handle mid-cycle group reassignment?**
A teacher realises after week one that a student was placed in the wrong group. Moving them to a different group mid-cycle means they receive a different booklet for the second week. How does the concept map handle a student who has partial coverage from one group and then joins another? Is this tracked at the group level or the individual level?

**4. What is the minimum viable concept sequence for a first-time teacher?**
If a new teacher has no community spine to import and no prior concept map, how much curriculum mapping do they have to do before generating the first booklet? Is there a way to infer a reasonable concept sequence from the subject, grade level, and a brief description of where the class currently is?

**5. How printable is the output really at scale?**
The calculus section HTML has basic print CSS. A production booklet printed on 30 different school printers, on different paper stocks, at different print quality settings, needs to look professional in all of those contexts. How much print testing is needed before the product can make a print-quality guarantee? What happens when the output looks bad on a specific printer configuration?

### Technical Questions

**6. What is the content accuracy strategy for subjects outside STEM?**
For mathematics and science, factual accuracy can be checked algorithmically in many cases. For history, literature, and social studies, factual accuracy requires domain knowledge that is harder to validate automatically. What is the quality checker doing for a Grade 8 Civil War section? How does the system catch a historically inaccurate characterisation before the teacher sees it?

**7. How does the system handle subjects with no community spine yet?**
In early months, the community will have configurations for mathematics and ELA. A teacher wanting to generate for Grade 5 Art or Grade 9 Economics has no community spine to import. What is the experience for those teachers? Does the system generate a suggested spine from the subject and grade level as a starting point? How good is that suggestion?

**8. What is the latency target for a full booklet generation?**
A teacher who clicks generate and waits 20 minutes will not use the tool regularly. A teacher who waits 3 minutes will. What is the target generation time for a 3-section, 3-group booklet (9 section generations plus assembly and QC)? What architectural decisions are required to hit that target reliably?

**9. How does the system handle curriculum standards alignment?**
Many teachers are required to align materials to state or national standards (Common Core, NGSS, etc.). Does the generated booklet need to show standards alignment? Does the teacher have to input which standards they are targeting, or can the system infer alignment from the concept description? What happens when the teacher's concept description does not align clearly to a standard?

### Community Questions

**10. How do you seed the community before launch?**
A community with nothing in it is worse than no community — it signals low adoption. Who are the first 20 teachers who generate excellent booklets and share their configurations? How do you find them, work with them closely during the pilot, and get their configurations into the community before public launch? What do you offer them in exchange?

**11. What is the moderation strategy?**
When the community has 500 configurations, some will be low quality. Some may contain inappropriate content. Some may be generated by teachers who never actually used the booklet in a classroom. How does the platform distinguish validated from unvalidated configurations? Who moderates and at what scale? Is it entirely rating-based or does there need to be human review?

**12. What stops a competitor from harvesting the community configurations?**
If configurations are visible to all registered teachers, a competitor could sign up as a teacher, harvest the top 100 configurations, and offer them on a competing platform. How is the community data protected? Is it behind login only? Are configurations watermarked or attribution-tracked in a way that makes harvesting identifiable?

### Market Questions

**13. What is the right first subject and grade level to go deep on?**
Rather than trying to support all subjects and grade levels from launch, which one subject and grade level produces the most compelling first booklets and has the most motivated early adopters? Mathematics and Grade 6–8 is a hypothesis. Is there evidence to support it or challenge it?

**14. How do you navigate AI content policies in districts that have restricted AI tools?**
Some districts have banned or restricted AI-generated content in classrooms. This product generates content that students read — even if teacher-reviewed and approved. How does the product communicate that the teacher reviewed and approved every booklet? Is there a review trail that administrators can audit? What is the response to a district that says "we don't allow AI-generated student materials"?

**15. What is the unit economics at the individual teacher price point?**
At $25–$40/month per teacher, what is the cost per booklet generation including API costs, infrastructure, and support? What teacher usage pattern (how many booklets per month, how many groups, what depth setting) produces a sustainable margin? At what scale does the individual teacher subscription become unprofitable if API costs are not managed carefully?

**16. How do you compete if a major platform copies the model?**
Google Classroom, Microsoft Teams for Education, or Khan Academy could build a version of this. Their distribution advantage is enormous — they already have teachers on their platforms. What is the defence? The community configurations, the concept map data, the teacher relationships — how long does it take for those to become defensible enough that a late entrant cannot simply outspend you?

---

## Part 8 — Recommended Next Steps

In priority order, before any further product decisions are made:

**1. Validate generation quality across three subjects**
Generate booklets for Grade 6 Mathematics, Grade 8 English Language Arts, and one science subject. Have five experienced teachers in each subject review them blind — without knowing they are AI-generated. Record what they correct, what they trust, what they would not use. This gives the honest quality baseline.

**2. Run one real classroom pilot**
Two to four teachers, one subject, one term. Generate booklets for their groups, let them use the material, record teacher time spent on setup and review, collect student outcome data. This is the only way to find the failure modes that desk evaluation cannot surface.

**3. Time the complete teacher workflow**
Onboarding a new teacher from zero to first approved booklet. Record every minute. Identify where time is spent and where friction occurs. The target is under two hours total for setup and under 20 minutes for each subsequent generation cycle.

**4. Build the print test matrix**
Generate the same booklet and print it on five different printer types at three different quality settings. Document what breaks. Fix the print CSS until the output is consistently professional across all tested configurations.

**5. Identify the first ten community seed teachers**
Before the community is built, know who the first ten teachers are who will populate it. Work with them closely during the pilot. Their configurations need to be in the community on day one of public access.

---

*End of Proposal v1.0*  
*Questions in Part 7 are the active thinking agenda — none are resolved.*
