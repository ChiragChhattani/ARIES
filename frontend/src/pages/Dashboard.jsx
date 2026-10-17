import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { createInterview, listInterviews } from "../services/api";

const FIELD_DEFAULTS = {
  frontend_development: {
    description: 'We are looking for a Frontend Developer proficient in React, JavaScript/TypeScript, and modern CSS. The role involves building responsive, accessible UIs and collaborating with design and backend teams.',
    skills: 'React, JavaScript, TypeScript, HTML, CSS',
    competencies: [
      {name: 'JavaScript Proficiency', description: 'Understanding of modern JS including ES6+, async/await, and DOM manipulation'},
      {name: 'React/Framework Knowledge', description: 'Ability to build and manage React components, hooks, and state'},
      {name: 'CSS & Responsive Design', description: 'Styling skills and responsive design principles'}
    ]
  },
  backend_development: {
    description: 'We are looking for a Backend Developer with strong expertise in REST API design, database management, authentication, and system design.',
    skills: 'Python or Node.js, REST APIs, SQL, Redis, system design',
    competencies: [
      {name: 'API Design', description: 'Designing RESTful APIs with proper authentication and error handling'},
      {name: 'Database Knowledge', description: 'SQL queries, indexing, and ORM usage'},
      {name: 'System Design', description: 'Ability to design scalable backend services'}
    ]
  },
  generative_ai: {
    description: 'We are looking for an AI Engineer specializing in Generative AI. The role involves building LLM-powered applications using RAG, embeddings, vector databases, tool calling, and agent orchestration frameworks like LangGraph or AutoGen.',
    skills: 'Python, LLMs, RAG, LangGraph or AutoGen, embeddings, vector databases',
    competencies: [
      {name: 'LLM Fundamentals', description: 'Understanding of large language models, tokenization, and inference'},
      {name: 'RAG & Embeddings', description: 'Building retrieval-augmented generation systems with vector databases'},
      {name: 'Agent Orchestration', description: 'Building multi-step agents using frameworks like LangGraph or AutoGen'},
      {name: 'Evaluation & Safety', description: 'Evaluating LLM outputs and implementing guardrails'}
    ]
  },
  ai_ml: {
    description: 'We are looking for an ML Engineer to build, train, and deploy machine learning models. The role involves data preprocessing, feature engineering, model evaluation, and MLOps.',
    skills: 'Python, scikit-learn, TensorFlow or PyTorch, statistics, MLOps',
    competencies: [
      {name: 'ML Algorithms', description: 'Knowledge of supervised, unsupervised, and reinforcement learning'},
      {name: 'Model Evaluation', description: 'Cross-validation, metrics, and avoiding overfitting'},
      {name: 'Feature Engineering', description: 'Preprocessing, encoding, and transforming data for models'}
    ]
  },
  data_science: {
    description: 'We are looking for a Data Scientist to derive insights from data, build predictive models, and communicate findings to stakeholders.',
    skills: 'Python, SQL, statistics, Pandas, data visualization',
    competencies: [
      {name: 'Statistical Analysis', description: 'Hypothesis testing, distributions, and statistical significance'},
      {name: 'Data Wrangling', description: 'Cleaning and transforming data with Pandas or SQL'},
      {name: 'Communication', description: 'Explaining data findings to non-technical stakeholders'}
    ]
  },
  data_engineering: {
    description: 'We are looking for a Data Engineer to build and maintain data pipelines, warehouses, and streaming infrastructure.',
    skills: 'Python, Spark, Airflow, SQL, cloud data platforms, Kafka',
    competencies: [
      {name: 'Pipeline Development', description: 'Building ETL/ELT data pipelines'},
      {name: 'Data Warehousing', description: 'Designing and managing data warehouses'},
      {name: 'Cloud Platforms', description: 'Working with cloud-native data tools'}
    ]
  },
  devops_cloud: {
    description: 'We are looking for a DevOps/Cloud Engineer to manage CI/CD pipelines, container orchestration, cloud infrastructure, and monitoring systems.',
    skills: 'Docker, Kubernetes, Terraform, CI/CD, AWS or GCP',
    competencies: [
      {name: 'CI/CD Pipelines', description: 'Building automated build, test, and deploy pipelines'},
      {name: 'Container Orchestration', description: 'Docker and Kubernetes knowledge'},
      {name: 'Cloud Infrastructure', description: 'Provisioning and managing cloud resources'}
    ]
  },
  software_engineering: {
    description: 'We are looking for a Software Engineer with strong fundamentals in data structures, algorithms, and system design.',
    skills: 'Data structures, algorithms, OOP, design patterns, system design',
    competencies: [
      {name: 'Algorithms & Data Structures', description: 'Problem solving with efficient algorithms'},
      {name: 'System Design', description: 'Designing scalable software systems'},
      {name: 'Code Quality', description: 'Writing clean, maintainable, tested code'}
    ]
  },
  fullstack_development: {
    description: 'We are looking for a Full-Stack Developer proficient in both frontend and backend technologies.',
    skills: 'React, Node.js or Python, REST APIs, SQL, JavaScript',
    competencies: [
      {name: 'Frontend Development', description: 'Building UIs with React or similar frameworks'},
      {name: 'Backend Development', description: 'Building server-side APIs and services'},
      {name: 'Database Management', description: 'Working with SQL and NoSQL databases'}
    ]
  },
  electrical_engineering: {
    description: 'We are looking for an Electrical Engineer with expertise in circuit design, power systems, and electrical machines.',
    skills: 'Circuit analysis, power systems, electrical machines, MATLAB, control systems',
    competencies: [
      {name: 'Circuit Analysis', description: 'Analyzing AC/DC circuits and electrical networks'},
      {name: 'Power Systems', description: 'Knowledge of power generation and distribution'},
      {name: 'Control Systems', description: 'Understanding of feedback control and stability'}
    ]
  },
  electronics_embedded: {
    description: 'We are looking for an Embedded Systems Engineer to design and program embedded hardware and firmware.',
    skills: 'C/C++, microcontrollers, RTOS, I2C/SPI/UART, PCB design',
    competencies: [
      {name: 'Embedded Programming', description: 'Writing firmware in C/C++ for microcontrollers'},
      {name: 'Hardware Interfacing', description: 'Communication protocols and peripheral integration'},
      {name: 'RTOS', description: 'Real-time operating system concepts and task management'}
    ]
  },
  mechanical_engineering: {
    description: 'We are looking for a Mechanical Engineer with knowledge of thermodynamics, manufacturing, and design.',
    skills: 'CAD (SolidWorks/AutoCAD), thermodynamics, fluid mechanics, materials science',
    competencies: [
      {name: 'Engineering Design', description: 'CAD and design principles'},
      {name: 'Thermal & Fluid Systems', description: 'Thermodynamics and fluid mechanics'},
      {name: 'Manufacturing', description: 'Manufacturing processes and quality control'}
    ]
  },
  civil_engineering: {
    description: 'We are looking for a Civil Engineer with skills in structural analysis, construction management, and geotechnics.',
    skills: 'Structural analysis, AutoCAD, construction management, geotechnics',
    competencies: [
      {name: 'Structural Analysis', description: 'Analyzing structural loads and designs'},
      {name: 'Construction Management', description: 'Planning and managing construction projects'},
      {name: 'Materials Knowledge', description: 'Properties and uses of construction materials'}
    ]
  },
  product_management: {
    description: 'We are looking for a Product Manager to define product strategy, prioritize features, and drive cross-functional execution.',
    skills: 'Product strategy, roadmapping, metrics, Agile, stakeholder communication',
    competencies: [
      {name: 'Product Strategy', description: 'Defining vision, goals, and roadmap'},
      {name: 'Prioritization', description: 'Using frameworks like RICE or ICE to prioritize'},
      {name: 'Stakeholder Management', description: 'Communicating with engineering, design, and business teams'}
    ]
  },
  business_analyst: {
    description: 'We are looking for a Business Analyst to gather requirements, analyze data, and bridge business and technical teams.',
    skills: 'Requirements gathering, SQL, process mapping, communication, data analysis',
    competencies: [
      {name: 'Requirements Gathering', description: 'Eliciting and documenting business requirements'},
      {name: 'Data Analysis', description: 'Analyzing data to support business decisions'},
      {name: 'Stakeholder Communication', description: 'Working with technical and business stakeholders'}
    ]
  },
  ui_ux_design: {
    description: 'We are looking for a UI/UX Designer to create user-centered designs, wireframes, and prototypes.',
    skills: 'Figma, user research, wireframing, prototyping, usability testing',
    competencies: [
      {name: 'User Research', description: 'Conducting user interviews and usability testing'},
      {name: 'Visual Design', description: 'Creating aesthetically pleasing and functional designs'},
      {name: 'Prototyping', description: 'Building interactive prototypes in Figma or similar'}
    ]
  },
  cybersecurity: {
    description: 'We are looking for a Cybersecurity Engineer to protect systems, networks, and data from security threats.',
    skills: 'Network security, penetration testing, cryptography, OWASP, incident response',
    competencies: [
      {name: 'Threat Analysis', description: 'Identifying and assessing security vulnerabilities'},
      {name: 'Security Protocols', description: 'Implementing cryptography and secure protocols'},
      {name: 'Incident Response', description: 'Detecting, containing, and recovering from security incidents'}
    ]
  },
  qa_testing: {
    description: 'We are looking for a QA Engineer to ensure product quality through manual and automated testing.',
    skills: 'Test planning, Selenium or Playwright, API testing, CI integration, bug tracking',
    competencies: [
      {name: 'Test Planning', description: 'Designing test plans and test cases'},
      {name: 'Test Automation', description: 'Writing automated tests with Selenium, Playwright, or pytest'},
      {name: 'API Testing', description: 'Testing REST APIs with Postman or similar'}
    ]
  },
  hr_recruitment: {
    description: 'We are looking for an HR/Recruitment specialist to attract, assess, and onboard top talent.',
    skills: 'Talent acquisition, HRIS, interviewing, labour law, onboarding',
    competencies: [
      {name: 'Talent Acquisition', description: 'Sourcing and screening candidates'},
      {name: 'People Management', description: 'Employee relations and performance management'},
      {name: 'Compliance', description: 'Labour law and HR compliance knowledge'}
    ]
  },
  custom: {
    description: '',
    skills: '',
    competencies: [
      {name: 'Domain Knowledge', description: 'Core concepts and principles relevant to the role'},
      {name: 'Problem Solving', description: 'Ability to analyze and solve domain-specific problems'},
      {name: 'Communication', description: 'Ability to explain technical concepts clearly'}
    ]
  }
};

export default function Dashboard() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    field: '',
    customField: '',
    jobTitle: '',
    jobDescription: '',
    skills: '',
    experienceLevel: 'mid_level',
    difficulty: 'medium',
    maxQuestions: 5
  });

  const [errors, setErrors] = useState({});
  const [userEditedDescription, setUserEditedDescription] = useState(false);
  const [userEditedSkills, setUserEditedSkills] = useState(false);

  useEffect(() => {
    fetchSessions();
  }, []);

  useEffect(() => {
    if (formData.field && FIELD_DEFAULTS[formData.field]) {
      const defaults = FIELD_DEFAULTS[formData.field];
      setFormData(prev => ({
        ...prev,
        jobDescription: userEditedDescription ? prev.jobDescription : defaults.description,
        skills: userEditedSkills ? prev.skills : defaults.skills
      }));
    }
  }, [formData.field, userEditedDescription, userEditedSkills]);

  async function fetchSessions() {
    try {
      const data = await listInterviews();
      setSessions(data.sessions);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  function validate() {
    const newErrors = {};
    if (!formData.field) newErrors.field = 'Field is required';
    if (formData.field === 'custom' && !formData.customField.trim()) newErrors.customField = 'Custom field name is required';
    if (!formData.jobTitle.trim()) newErrors.jobTitle = 'Job title is required';
    if (!formData.jobDescription.trim() || formData.jobDescription.length < 50) newErrors.jobDescription = 'Job description must be at least 50 characters';
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!validate()) return;

    setCreating(true);
    try {
      const submissionData = { ...formData };
      if (submissionData.field && FIELD_DEFAULTS[submissionData.field]) {
          submissionData.competencies = FIELD_DEFAULTS[submissionData.field].competencies;
      } else {
          submissionData.competencies = [];
      }
      
      const session = await createInterview(submissionData);
      navigate(`/interview/${session.session_id}`);
    } catch (e) {
      alert("Failed to create interview. Is the backend running?");
      console.error(e);
      setCreating(false);
    }
  }

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors(prev => ({ ...prev, [name]: null }));
    
    if (name === 'jobDescription') setUserEditedDescription(true);
    if (name === 'skills') setUserEditedSkills(true);
  };

  return (
    <div className="space-y-8">
      {/* Top Banner / Actions */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[#0E131F]/90 backdrop-blur-xl p-6 sm:p-8 rounded-2xl border border-slate-800/80 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-40 bg-gradient-to-bl from-violet-600/10 via-cyan-500/5 to-transparent pointer-events-none rounded-tr-2xl"></div>
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-sm shadow-cyan-400/50"></span>
            <span className="text-xs uppercase tracking-wider font-semibold text-cyan-400">Technical Assessment Hub</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">Interviews & Evaluations</h1>
          <p className="text-slate-400 text-sm mt-1 max-w-xl">
            Configure role-tailored technical interviews with live proctoring, AI orchestration, and objective rubric scoring.
          </p>
        </div>
        <button 
          onClick={() => setShowForm(!showForm)} 
          className={`relative z-10 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all duration-200 active:scale-[0.98] ${
            showForm
              ? "bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
              : "bg-gradient-to-r from-violet-600 via-indigo-600 to-cyan-600 hover:from-violet-500 hover:to-cyan-500 text-white shadow-lg shadow-violet-600/25 border border-violet-400/20"
          }`}
        >
          {showForm ? "Cancel Creation" : "+ Create New Interview"}
        </button>
      </div>

      {/* Creation Form Modal/Card */}
      {showForm && (
        <div className="bg-[#0E131F]/95 backdrop-blur-2xl p-6 sm:p-8 rounded-2xl border border-violet-500/30 shadow-2xl shadow-violet-950/20 relative animate-fade-in">
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-800">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <span className="text-violet-400">⚡</span> Setup New Interview Session
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">Customize the position requirements and competency rubric</p>
            </div>
            <span className="text-xs font-mono bg-violet-500/10 text-violet-300 border border-violet-500/20 px-2.5 py-1 rounded-md">
              AI Powered
            </span>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                  Professional Field <span className="text-rose-400">*</span>
                </label>
                <select 
                  name="field" 
                  value={formData.field} 
                  onChange={handleInputChange}
                  className="w-full bg-[#080B11] border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all"
                >
                  <option value="" className="bg-slate-900 text-slate-400">Select a field...</option>
                  <optgroup label="Software & IT" className="bg-slate-900 text-slate-300 font-semibold">
                    <option value="software_engineering" className="font-normal">Software Engineering/SDE</option>
                    <option value="frontend_development" className="font-normal">Frontend Development</option>
                    <option value="backend_development" className="font-normal">Backend Development</option>
                    <option value="fullstack_development" className="font-normal">Full-Stack Development</option>
                    <option value="devops_cloud" className="font-normal">DevOps/Cloud Engineering</option>
                    <option value="cybersecurity" className="font-normal">Cybersecurity</option>
                    <option value="qa_testing" className="font-normal">QA/Software Testing</option>
                  </optgroup>
                  <optgroup label="Data & AI" className="bg-slate-900 text-slate-300 font-semibold">
                    <option value="ai_ml" className="font-normal">AI/Machine Learning</option>
                    <option value="generative_ai" className="font-normal">Generative AI/Agentic AI</option>
                    <option value="data_science" className="font-normal">Data Science/Analytics</option>
                    <option value="data_engineering" className="font-normal">Data Engineering</option>
                  </optgroup>
                  <optgroup label="Core Engineering" className="bg-slate-900 text-slate-300 font-semibold">
                    <option value="electrical_engineering" className="font-normal">Electrical Engineering</option>
                    <option value="electronics_embedded" className="font-normal">Electronics/Embedded Systems</option>
                    <option value="mechanical_engineering" className="font-normal">Mechanical Engineering</option>
                    <option value="civil_engineering" className="font-normal">Civil Engineering</option>
                  </optgroup>
                  <optgroup label="Business & Design" className="bg-slate-900 text-slate-300 font-semibold">
                    <option value="product_management" className="font-normal">Product Management</option>
                    <option value="business_analyst" className="font-normal">Business Analyst</option>
                    <option value="ui_ux_design" className="font-normal">UI/UX Design</option>
                    <option value="hr_recruitment" className="font-normal">HR/Recruitment</option>
                    <option value="custom" className="font-normal">Custom/Other</option>
                  </optgroup>
                </select>
                {errors.field && <p className="text-rose-400 text-xs mt-1.5 font-medium">{errors.field}</p>}
              </div>

              {formData.field === 'custom' ? (
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                    Custom Field Name <span className="text-rose-400">*</span>
                  </label>
                  <input 
                    type="text" 
                    name="customField" 
                    value={formData.customField} 
                    onChange={handleInputChange}
                    placeholder="e.g. Quantum Computing"
                    className="w-full bg-[#080B11] border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all"
                  />
                  {errors.customField && <p className="text-rose-400 text-xs mt-1.5 font-medium">{errors.customField}</p>}
                </div>
              ) : (
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                    Job Title <span className="text-rose-400">*</span>
                  </label>
                  <input 
                    type="text" 
                    name="jobTitle" 
                    value={formData.jobTitle} 
                    onChange={handleInputChange}
                    placeholder="e.g. Senior Backend Engineer"
                    className="w-full bg-[#080B11] border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all"
                  />
                  {errors.jobTitle && <p className="text-rose-400 text-xs mt-1.5 font-medium">{errors.jobTitle}</p>}
                </div>
              )}
            </div>

            {formData.field === 'custom' && (
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                  Job Title <span className="text-rose-400">*</span>
                </label>
                <input 
                  type="text" 
                  name="jobTitle" 
                  value={formData.jobTitle} 
                  onChange={handleInputChange}
                  placeholder="e.g. Lead Research Scientist"
                  className="w-full bg-[#080B11] border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all"
                />
                {errors.jobTitle && <p className="text-rose-400 text-xs mt-1.5 font-medium">{errors.jobTitle}</p>}
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Job Description <span className="text-rose-400">*</span> <span className="text-slate-500 font-normal lowercase">(min 50 characters)</span>
              </label>
              <textarea 
                name="jobDescription" 
                value={formData.jobDescription} 
                onChange={handleInputChange}
                rows="3"
                placeholder="Describe role responsibilities, key technologies, and expectations..."
                className="w-full bg-[#080B11] border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all"
              ></textarea>
              {errors.jobDescription && <p className="text-rose-400 text-xs mt-1.5 font-medium">{errors.jobDescription}</p>}
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Required Skills <span className="text-slate-500 font-normal lowercase">(comma-separated)</span>
              </label>
              <input 
                type="text" 
                name="skills" 
                value={formData.skills} 
                onChange={handleInputChange}
                placeholder="e.g. Python, FastAPI, Docker, Microservices, Redis"
                className="w-full bg-[#080B11] border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">Experience Level</label>
                <select 
                  name="experienceLevel" 
                  value={formData.experienceLevel} 
                  onChange={handleInputChange}
                  className="w-full bg-[#080B11] border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all"
                >
                  <option value="fresher" className="bg-slate-900">Fresher (0-1 yrs)</option>
                  <option value="junior" className="bg-slate-900">Junior (1-3 yrs)</option>
                  <option value="mid_level" className="bg-slate-900">Mid-Level (3-5 yrs)</option>
                  <option value="senior" className="bg-slate-900">Senior (5+ yrs)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">Target Difficulty</label>
                <select 
                  name="difficulty" 
                  value={formData.difficulty} 
                  onChange={handleInputChange}
                  className="w-full bg-[#080B11] border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all"
                >
                  <option value="easy" className="bg-slate-900">Easy (Foundational)</option>
                  <option value="medium" className="bg-slate-900">Medium (Applied Practical)</option>
                  <option value="hard" className="bg-slate-900">Hard (Deep Architecture)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">Max Questions</label>
                <input 
                  type="number" 
                  name="maxQuestions" 
                  value={formData.maxQuestions} 
                  onChange={handleInputChange}
                  min="3" 
                  max="20"
                  className="w-full bg-[#080B11] border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all font-mono"
                />
              </div>
            </div>

            <div className="pt-4 flex justify-end gap-3 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="px-5 py-2.5 rounded-xl text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition"
              >
                Cancel
              </button>
              <button 
                type="submit" 
                disabled={creating}
                className="bg-gradient-to-r from-violet-600 via-indigo-600 to-cyan-600 hover:from-violet-500 hover:to-cyan-500 text-white px-6 py-2.5 rounded-xl font-semibold text-sm shadow-lg shadow-violet-600/30 transition-all disabled:opacity-50"
              >
                {creating ? "Configuring Session..." : "Launch Interview"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Session Records List */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <span>Recent Sessions</span>
            <span className="text-xs font-mono bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full border border-slate-700/60">
              {sessions.length}
            </span>
          </h2>
        </div>

        {loading ? (
          <div className="text-center py-16 text-slate-500 flex flex-col items-center justify-center">
            <div className="w-8 h-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin mb-3"></div>
            <p className="text-sm">Loading interview records...</p>
          </div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-16 bg-[#0E131F]/40 rounded-2xl border border-dashed border-slate-800 p-8">
            <div className="w-12 h-12 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center mx-auto mb-3 text-slate-500">
              📋
            </div>
            <h3 className="text-slate-300 font-semibold mb-1">No interview sessions found</h3>
            <p className="text-slate-500 text-xs max-w-sm mx-auto mb-4">
              Get started by creating your first automated technical interview session above.
            </p>
            <button
              onClick={() => setShowForm(true)}
              className="text-xs font-semibold text-violet-400 hover:text-violet-300 transition"
            >
              + Create Interview Now
            </button>
          </div>
        ) : (
          <div className="grid gap-3.5">
            {sessions.map((s) => (
              <div 
                key={s.session_id} 
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#0E131F]/90 hover:bg-[#121929] p-5 rounded-xl border border-slate-800/90 hover:border-slate-700 transition-all duration-200 group shadow-md"
              >
                <div>
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <h3 className="font-bold text-white text-base group-hover:text-violet-300 transition-colors">
                      {s.job_title}
                    </h3>
                    {s.job_description?.field && (
                      <span className="text-[11px] font-medium bg-slate-800/80 text-slate-400 px-2 py-0.5 rounded border border-slate-700/50 capitalize">
                        {s.job_description.field.replace(/_/g, " ")}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-400 mt-1.5 flex items-center gap-3 font-mono">
                    <span className="text-slate-500">ID: <span className="text-slate-300">{s.session_id.split("-")[0]}</span></span>
                    <span className="w-1 h-1 bg-slate-700 rounded-full"></span>
                    <span className="text-slate-400">{new Date(s.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                  </div>
                </div>
                
                <div className="flex items-center gap-3 self-end sm:self-center">
                  <span className={`text-xs px-2.5 py-1 rounded-full font-medium tracking-wide uppercase ${
                    s.status === 'COMPLETED' ? 'bg-blue-500/10 text-blue-300 border border-blue-500/25' :
                    s.status === 'REPORT_READY' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/25' :
                    s.status === 'IN_PROGRESS' ? 'bg-amber-500/10 text-amber-300 border border-amber-500/25 animate-pulse' :
                    'bg-slate-800 text-slate-400 border border-slate-700'
                  }`}>
                    {s.status.replace("_", " ")}
                  </span>
                  
                  {s.status === 'REPORT_READY' ? (
                    <button 
                      onClick={() => navigate(`/report/${s.session_id}`)} 
                      className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 transition-all flex items-center gap-1.5"
                    >
                      <span>View Report</span>
                      <span>→</span>
                    </button>
                  ) : (
                    <button 
                      onClick={() => navigate(`/interview/${s.session_id}`)} 
                      className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white shadow-sm shadow-violet-500/25 transition-all flex items-center gap-1.5"
                    >
                      <span>Open Room</span>
                      <span>→</span>
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
