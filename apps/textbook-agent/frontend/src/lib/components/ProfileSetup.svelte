<script lang="ts">
	import type {
		Brevity,
		ExplanationStyle,
		ExampleStyle,
		GradeBand,
		ReadingLevel,
		TeacherProfileUpsertRequest,
		TeacherRole,
		Tone
	} from '$lib/types';

	interface Props {
		onsubmit: (data: TeacherProfileUpsertRequest) => void;
		disabled?: boolean;
		initialData?: TeacherProfileUpsertRequest | null;
		submitLabel?: string;
	}

	let {
		onsubmit,
		disabled = false,
		initialData = null,
		submitLabel = 'Complete Setup'
	}: Props = $props();

	let teacherRole: TeacherRole = $state('teacher');
	let defaultGradeBand: GradeBand = $state('high_school');
	let defaultAudienceDescription = $state('');
	let curriculumFramework = $state('');
	let classroomContext = $state('');
	let planningGoals = $state('');
	let schoolOrOrgName = $state('');
	let subjects: string[] = $state([]);
	let subjectInput = $state('');
	let tone: Tone = $state('supportive');
	let readingLevel: ReadingLevel = $state('standard');
	let explanationStyle: ExplanationStyle = $state('balanced');
	let exampleStyle: ExampleStyle = $state('everyday');
	let brevity: Brevity = $state('balanced');
	let useVisuals = $state(false);
	let printFirst = $state(false);
	let morePractice = $state(false);
	let keepShort = $state(false);
	let initializedFromProps = $state(false);

	$effect(() => {
		if (!initialData || initializedFromProps) {
			return;
		}

		teacherRole = initialData.teacher_role;
		defaultGradeBand = initialData.default_grade_band;
		defaultAudienceDescription = initialData.default_audience_description;
		curriculumFramework = initialData.curriculum_framework;
		classroomContext = initialData.classroom_context;
		planningGoals = initialData.planning_goals;
		schoolOrOrgName = initialData.school_or_org_name;
		subjects = [...initialData.subjects];
		tone = initialData.delivery_preferences.tone;
		readingLevel = initialData.delivery_preferences.reading_level;
		explanationStyle = initialData.delivery_preferences.explanation_style;
		exampleStyle = initialData.delivery_preferences.example_style;
		brevity = initialData.delivery_preferences.brevity;
		useVisuals = initialData.delivery_preferences.use_visuals;
		printFirst = initialData.delivery_preferences.print_first;
		morePractice = initialData.delivery_preferences.more_practice;
		keepShort = initialData.delivery_preferences.keep_short;
		initializedFromProps = true;
	});

	function addSubject() {
		const tag = subjectInput.trim().toLowerCase();
		if (tag && !subjects.includes(tag)) {
			subjects = [...subjects, tag];
		}
		subjectInput = '';
	}

	function removeSubject(tag: string) {
		subjects = subjects.filter((entry) => entry !== tag);
	}

	function handleSubjectKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' || event.key === ',') {
			event.preventDefault();
			addSubject();
		}
	}

	function handleSubmit() {
		onsubmit({
			teacher_role: teacherRole,
			subjects,
			default_grade_band: defaultGradeBand,
			default_audience_description: defaultAudienceDescription,
			curriculum_framework: curriculumFramework,
			classroom_context: classroomContext,
			planning_goals: planningGoals,
			school_or_org_name: schoolOrOrgName,
			delivery_preferences: {
				tone,
				reading_level: readingLevel,
				explanation_style: explanationStyle,
				example_style: exampleStyle,
				brevity,
				use_visuals: useVisuals,
				print_first: printFirst,
				more_practice: morePractice,
				keep_short: keepShort
			}
		});
	}
</script>

<form onsubmit={(event: Event) => { event.preventDefault(); handleSubmit(); }} class="profile-form">
	<div class="form-section">
		<h3>Teacher Profile</h3>
		<p class="hint">Save the teaching context and defaults you want the product to remember between sessions.</p>

		<label>
			Teaching role
			<select bind:value={teacherRole}>
				<option value="teacher">Teacher</option>
				<option value="tutor">Tutor</option>
				<option value="homeschool">Homeschool educator</option>
				<option value="instructor">Instructor</option>
			</select>
		</label>

		<label>
			School or organisation (optional)
			<input type="text" bind:value={schoolOrOrgName} placeholder="e.g. Riverside High School" />
		</label>

		<div>
			<p class="field-title">Subjects you teach</p>
			<p class="hint">Add one or more subjects so the dashboard and Studio can adapt recommendations.</p>
			<div class="tag-input-wrapper">
				<div class="tags">
					{#each subjects as tag}
						<span class="tag">
							{tag}
							<button type="button" class="tag-remove" onclick={() => removeSubject(tag)}>&times;</button>
						</span>
					{/each}
				</div>
				<input
					type="text"
					bind:value={subjectInput}
					onkeydown={handleSubjectKeydown}
					placeholder="Type a subject and press Enter"
				/>
			</div>
		</div>
	</div>

	<div class="form-section">
		<h3>Default Classroom Context</h3>

		<label>
			Default grade band
			<select bind:value={defaultGradeBand}>
				<option value="primary">Primary</option>
				<option value="middle">Middle school</option>
				<option value="high_school">High school</option>
				<option value="undergraduate">Undergraduate</option>
				<option value="adult">Adult learners</option>
			</select>
		</label>

		<label>
			Default audience description
			<textarea
				bind:value={defaultAudienceDescription}
				rows="3"
				placeholder="e.g. Year 9 mixed-ability science class with a wide reading range"
			></textarea>
		</label>

		<label>
			Curriculum or framework (optional)
			<input
				type="text"
				bind:value={curriculumFramework}
				placeholder="e.g. GCSE AQA, Common Core, IB MYP"
			/>
		</label>

		<label>
			Classroom context (optional)
			<textarea
				bind:value={classroomContext}
				rows="4"
				placeholder="e.g. Limited devices, mixed prior knowledge, several EAL learners, strong response to worked examples"
			></textarea>
		</label>
	</div>

	<div class="form-section">
		<h3>Lesson Defaults</h3>
		<p class="hint">These become starting defaults in Studio. You can still change them for each lesson.</p>

		<label>
			Tone
			<select bind:value={tone}>
				<option value="supportive">Supportive</option>
				<option value="neutral">Neutral</option>
				<option value="rigorous">Rigorous</option>
			</select>
		</label>

		<label>
			Reading level
			<select bind:value={readingLevel}>
				<option value="simple">Simple</option>
				<option value="standard">Standard</option>
				<option value="advanced">Advanced</option>
			</select>
		</label>

		<label>
			Explanation style
			<select bind:value={explanationStyle}>
				<option value="concrete-first">Concrete examples first</option>
				<option value="concept-first">Concept first</option>
				<option value="balanced">Balanced</option>
			</select>
		</label>

		<label>
			Example style
			<select bind:value={exampleStyle}>
				<option value="everyday">Everyday examples</option>
				<option value="academic">Academic examples</option>
				<option value="exam">Exam-style examples</option>
			</select>
		</label>

		<label>
			Brevity
			<select bind:value={brevity}>
				<option value="tight">Concise</option>
				<option value="balanced">Balanced</option>
				<option value="expanded">Expanded</option>
			</select>
		</label>

		<div class="toggle-grid">
			<label class="toggle-row">
				<input type="checkbox" bind:checked={useVisuals} />
				<span>Use visuals where they help</span>
			</label>
			<label class="toggle-row">
				<input type="checkbox" bind:checked={printFirst} />
				<span>Optimise for print layout</span>
			</label>
			<label class="toggle-row">
				<input type="checkbox" bind:checked={morePractice} />
				<span>Emphasise practice</span>
			</label>
			<label class="toggle-row">
				<input type="checkbox" bind:checked={keepShort} />
				<span>Keep lessons compact</span>
			</label>
		</div>
	</div>

	<div class="form-section">
		<h3>Product Goals</h3>

		<label>
			What do you want help with most?
			<textarea
				bind:value={planningGoals}
				rows="4"
				placeholder="e.g. Faster first drafts, better scaffolds for mixed-ability classes, stronger exam-style practice"
			></textarea>
		</label>
	</div>

	<button type="submit" class="submit-btn" {disabled}>{submitLabel}</button>
</form>

<style>
	.profile-form {
		display: flex;
		flex-direction: column;
		gap: 2rem;
		max-width: 680px;
	}

	.form-section {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}

	.form-section h3 {
		margin: 0;
		font-size: 1.2rem;
		font-weight: 700;
		letter-spacing: 0.01em;
		color: #1f2b34;
		border-bottom: 1px solid rgba(61, 47, 26, 0.25);
		padding-bottom: 0.55rem;
	}

	.hint {
		font-size: 0.92rem;
		line-height: 1.55;
		color: #5c554c;
		margin: 0;
	}

	label {
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
		font-size: 0.96rem;
		font-weight: 600;
		line-height: 1.4;
		color: #2b241d;
	}

	.field-title {
		margin: 0;
		font-size: 0.96rem;
		font-weight: 600;
		line-height: 1.4;
		color: #2b241d;
	}

	input, textarea, select {
		width: 100%;
		box-sizing: border-box;
		padding: 0.9rem 1rem;
		border: 1px solid rgba(53, 71, 86, 0.22);
		border-radius: 12px;
		background: rgba(255, 252, 247, 0.96);
		color: #1f2b34;
		font: inherit;
		font-weight: 500;
		line-height: 1.5;
		box-shadow:
			0 1px 0 rgba(255, 255, 255, 0.8) inset,
			0 10px 24px rgba(57, 44, 29, 0.05);
		transition:
			border-color 140ms ease,
			box-shadow 140ms ease,
			background-color 140ms ease;
	}

	input:focus, textarea:focus, select:focus {
		outline: none;
		border-color: rgba(54, 101, 130, 0.58);
		box-shadow:
			0 0 0 4px rgba(84, 135, 171, 0.16),
			0 12px 28px rgba(57, 44, 29, 0.08);
		background: #fffdf9;
	}

	input::placeholder,
	textarea::placeholder {
		color: #7a7167;
		font-weight: 400;
	}

	textarea {
		min-height: 6.5rem;
		resize: vertical;
	}

	.tag-input-wrapper {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.tag {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		padding: 0.45rem 0.75rem;
		background: rgba(54, 101, 130, 0.1);
		border: 1px solid rgba(54, 101, 130, 0.14);
		border-radius: 999px;
		font-size: 0.88rem;
		font-weight: 600;
		color: #2b5067;
	}

	.tag-remove {
		background: none;
		border: none;
		color: #5c554c;
		cursor: pointer;
		padding: 0;
		font-size: 1rem;
		line-height: 1;
	}

	.tag-remove:hover {
		color: #e57373;
	}

	.toggle-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 0.75rem;
	}

	.toggle-row {
		flex-direction: row;
		align-items: center;
		gap: 0.6rem;
		padding: 0.85rem 0.95rem;
		border: 1px solid rgba(53, 71, 86, 0.14);
		border-radius: 12px;
		background: rgba(255, 252, 247, 0.82);
	}

	.toggle-row input {
		width: auto;
		box-sizing: border-box;
		padding: 0;
		border: none;
		border-radius: 0;
		background: transparent;
		box-shadow: none;
		accent-color: #2b5067;
	}

	.submit-btn {
		align-self: flex-start;
		padding: 0.95rem 1.6rem;
		background: linear-gradient(135deg, #244560, #3f7598);
		color: #fff;
		border: none;
		border-radius: 999px;
		font-size: 1rem;
		font-weight: 700;
		letter-spacing: 0.01em;
		cursor: pointer;
		margin-top: 0.25rem;
		box-shadow: 0 16px 32px rgba(31, 61, 82, 0.2);
		transition:
			transform 140ms ease,
			box-shadow 140ms ease,
			filter 140ms ease;
	}

	.submit-btn:hover:not(:disabled) {
		transform: translateY(-1px);
		box-shadow: 0 18px 36px rgba(31, 61, 82, 0.24);
		filter: brightness(1.04);
	}

	.submit-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
		box-shadow: none;
	}

	@media (max-width: 640px) {
		.profile-form {
			gap: 1.75rem;
		}

		input, textarea, select {
			padding: 0.85rem 0.9rem;
		}

		.submit-btn {
			width: 100%;
		}
	}
</style>
