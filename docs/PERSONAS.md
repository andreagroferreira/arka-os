# ArkaOS Personas

The persona system lets you create custom AI personas from real people's content (YouTube, books, podcasts), then optionally clone them as ArkaOS agents that work alongside the built-in 65 agents.

## What Is a Persona

A persona is a voice and behavior profile built from analyzing someone's public content. ArkaOS extracts communication patterns, vocabulary, frameworks they use, opinions they hold, and how they structure arguments. The result is a profile that can generate content in that person's style.

Personas are separate from agents. An agent is a permanent member of a department with a role, behavioral DNA, and assigned skills. A persona is a voice profile that can exist independently or be cloned into an agent.

## Creating a Persona Through the Dashboard

Start the dashboard:

```bash
npx arkaos dashboard
```

Navigate to the **Personas** page (localhost:3333/personas).

### Step 1: Name and Describe

Give the persona a name and a short description of who they are:

```
Name: Alex Hormozi
Description: Business strategist known for offer creation, gym turnarounds,
             and scaling businesses. Direct communication style, uses
             analogies, values over everything.
```

### Step 2: Add Knowledge Sources

Point ArkaOS at the content to analyze. The more sources, the more accurate the persona.

```
Sources:
  - https://youtube.com/watch?v=video1  (100M Offers keynote)
  - https://youtube.com/watch?v=video2  (Pricing strategy talk)
  - https://youtube.com/watch?v=video3  (How to scale podcast)
```

Each source is ingested asynchronously:
1. YouTube videos are downloaded and transcribed with Whisper
2. PDFs are extracted and chunked
3. Web pages are fetched and cleaned

You can track progress on the **Tasks** page.

### Step 3: Define Traits (Optional)

Add explicit traits to guide the persona. These supplement what ArkaOS discovers from the content:

```
Traits:
  - Direct and no-nonsense
  - Uses simple analogies to explain complex ideas
  - Frames everything as value exchange
  - Avoids jargon and academic language
  - Loves concrete numbers and examples
```

### Step 4: Build

Click **Build Persona**. ArkaOS runs 5 analysis passes on the ingested content:

1. **Voice analysis** -- sentence structure, vocabulary level, cadence
2. **Framework extraction** -- recurring models and mental frameworks they use
3. **Opinion mapping** -- strong positions and beliefs
4. **Argument patterns** -- how they structure persuasion (examples first? data first?)
5. **Catchphrases** -- signature phrases and expressions

Building takes 2-5 minutes depending on the amount of source material.

### What You Get

A persona profile that includes:

```
PERSONA: Alex Hormozi

VOICE PROFILE:
  Sentence length: Short to medium (8-15 words average)
  Vocabulary level: Accessible (8th grade reading level)
  Tone: Confident, direct, occasionally provocative
  Cadence: Fast-paced, punch-line oriented

FRAMEWORKS USED:
  - Grand Slam Offer (value stack > price)
  - Lead magnets as trust builders
  - "Volume negates luck"
  - LTV > CAC as the only metric that matters

ARGUMENT PATTERN:
  1. Bold claim
  2. Personal story proving the claim
  3. Simple framework explaining why
  4. Concrete numbers as proof
  5. Action item for the listener

CATCHPHRASES:
  - "The goal isn't to make money, it's to make money make money"
  - "If you can't explain it simply, you don't understand it"
  - "Most people overestimate what they can do in a year..."

SAMPLE OUTPUT (writing in this persona's voice):
  "Here's the thing about pricing — most founders think
  lowering the price gets more customers. Wrong. Lowering
  the price gets worse customers. I learned this the hard
  way running gyms. We raised prices 3x and got 2x the
  customers. Why? Because the offer was so good, the price
  was irrelevant."
```

## Creating a Persona via API

```bash
curl -X POST http://localhost:3334/api/personas \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alex Hormozi",
    "description": "Business strategist, offer creation expert",
    "knowledge_sources": [
      "https://youtube.com/watch?v=video1",
      "https://youtube.com/watch?v=video2"
    ],
    "traits": ["direct", "uses-analogies", "value-focused", "no-jargon"]
  }'
```

Response:

```json
{
  "id": "persona-003",
  "name": "Alex Hormozi",
  "status": "building",
  "task_id": "task-0051"
}
```

Poll `GET /api/tasks/task-0051` to track build progress.

## Cloning a Persona to an Agent

Once a persona is built, you can clone it into an ArkaOS agent. The cloned agent gets a department assignment, behavioral DNA (auto-generated from the voice analysis), and can be assigned to skills.

### Through the Dashboard

On the persona's detail page, click **Clone to Agent**. Choose:
- **Department** -- where this agent belongs (e.g., sales, content, landing)
- **Role** -- what role they fill (e.g., "Offer Strategist", "Content Writer")

### Through the API

```bash
curl -X POST http://localhost:3334/api/personas/persona-003/clone \
  -H "Content-Type: application/json" \
  -d '{"department": "sales", "role": "Offer Strategist"}'
```

Response:

```json
{
  "agent_id": "sales-alex-hormozi",
  "agent_yaml": "departments/sales/agents/alex-hormozi.yaml",
  "status": "created"
}
```

The generated agent YAML includes:
- 4-framework behavioral DNA derived from the persona's voice analysis
- Department and tier assignment
- Skills the agent can execute (based on the persona's expertise)

### Using the Cloned Agent

After cloning, the agent is available like any other ArkaOS agent. You can reference it in workflow YAML files or the system will route to it when the persona's expertise matches:

```
/sales grand-slam-offer "fitness coaching program"
```

If the Hormozi persona is cloned into the sales department, it may be selected for offer-related tasks based on its expertise match.

## Future: AI-Powered Persona Building

The current system requires you to provide specific URLs. Future versions will support:

- **Auto-discovery** -- Give a name, ArkaOS finds their YouTube channel, podcast appearances, books, and blog posts automatically
- **Live updating** -- Persona updates when new content is published
- **Cross-referencing** -- Build a persona from multiple people (e.g., "Hormozi's offer strategy + Brunson's funnel thinking")
- **Persona conversations** -- Two personas debate a topic, you observe and extract insights

## Managing Personas

**List all personas:**

```bash
curl http://localhost:3334/api/personas
```

**View persona detail:**

```bash
curl http://localhost:3334/api/personas/persona-003
```

**Delete a persona:**

```bash
curl -X DELETE http://localhost:3334/api/personas/persona-003
```

Deleting a persona does not delete any cloned agents. Agents are independent once created.

## Persona vs Agent

| | Persona | Agent |
|---|---------|-------|
| **Purpose** | Voice and behavior profile | Department member with skills |
| **Created from** | External content (YouTube, books) | YAML definition with behavioral DNA |
| **Can execute skills** | No | Yes |
| **Part of a department** | No | Yes |
| **Has behavioral DNA** | Generated on clone | Defined in YAML |
| **Permanent** | Optional (can delete) | Yes (part of the system) |
| **Count** | Unlimited | 65 built-in + cloned |
