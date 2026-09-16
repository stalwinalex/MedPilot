import re
from typing import List, Dict, Optional, Tuple, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.models import ClassOccurrence, ClassTopic, Subject, Exam, Attendance, StudyTask
from app.services.exam_syllabus_ai_service import ExamSyllabusAIService


# Canonical MBBS Hierarchical Curriculum Syllabus Directory
CANONICAL_CURRICULUM_SYLLABUS: Dict[str, Dict[str, List[str]]] = {
    "anatomy": {
        "General Anatomy": [
            "Introduction to Anatomical Terms & Planes",
            "Classification of Bones & Cartilage",
            "Joints Classification & Mechanics",
            "Fascia & Principles of Muscle Innervation"
        ],
        "Upper Limb": [
            "Brachial Plexus",
            "Axillary Artery & Axilla",
            "Shoulder Joint & Rotator Cuff",
            "Cubital Fossa Boundaries & Contents",
            "Carpal Tunnel & Median Nerve",
            "Radial Nerve & Wrist Drop",
            "Ulnar Nerve & Claw Hand",
            "Spaces of Hand & Palmar Arches"
        ],
        "Lower Limb": [
            "Femoral Triangle Boundaries & Contents",
            "Femoral Canal & Femoral Hernia",
            "Popliteal Fossa Boundaries & Contents",
            "Gluteal Region & Sciatic Nerve",
            "Knee Joint, Menisci & Cruciate Ligaments",
            "Arches of Foot & Plantar Fascia"
        ],
        "Thorax": [
            "Coronary Circulation & Heart Anatomy",
            "Bronchopulmonary Segments & Lungs",
            "Mediastinum & Divisions",
            "Thoracic Duct & Azygos System",
            "Intercostal Spaces & Pleura"
        ],
        "Abdomen & Pelvis": [
            "Inguinal Canal & Hernia Anatomy",
            "Celiac Trunk & Blood Supply of Stomach",
            "Peritoneal Spaces & Lesser Sac",
            "Liver Anatomy & Biliary Tree",
            "Kidney Anatomy & Renal Fascia",
            "Uterus, Broad Ligament & Pelvic Diaphragm"
        ],
        "Head & Neck": [
            "Triangles of the Neck (Anterior & Posterior)",
            "Cranial Nerves (VII, IX, X, XII)",
            "Cavernous Sinus & Dural Venous Sinuses",
            "Circle of Willis & Brainstem",
            "Parotid Gland & Facial Nerve Relations",
            "Thyroid Gland & Blood Supply"
        ],
        "Neuroanatomy": [
            "Spinal Cord Tracts (Ascending & Descending)",
            "Internal Capsule & Blood Supply",
            "Ventricular System & CSF Circulation",
            "Cerebellum & Brainstem Nuclei"
        ],
        "Histology": [
            "Histology of Liver, Spleen & Kidney",
            "Histology of GI Tract (Stomach, Intestine)",
            "Histology of Cartilage & Bone",
            "Histology of Endocrine Glands"
        ],
        "Embryology": [
            "Pharyngeal Arches & Derivatives",
            "Neural Tube Development & Defects",
            "Development of Heart & Septal Defects",
            "Development of Gastrointestinal Tract"
        ]
    },
    "physiology": {
        "General Physiology": [
            "Cell Membrane Transport Mechanisms",
            "Resting Membrane Potential & Nernst Equation",
            "Body Fluid Compartments & Osmolarity",
            "Homeostasis & Feedback Mechanisms"
        ],
        "Nerve & Muscle": [
            "Action Potential & Refractory Periods",
            "Neuromuscular Junction & Synaptic Transmission",
            "Excitation-Contraction Coupling",
            "Molecular Basis of Muscle Contraction",
            "Myasthenia Gravis Pathophysiology"
        ],
        "Blood": [
            "Erythropoiesis & Iron Metabolism",
            "Hemostasis & Clotting Cascade",
            "Blood Groups (ABO & Rh) & Transfusion",
            "Immunity & White Blood Cell Functions",
            "Anemias Classification & Pathophysiology"
        ],
        "Cardiovascular System": [
            "Cardiac Cycle & Pressure-Volume Loops",
            "ECG Waves, Intervals & Arrhythmias",
            "Regulation of Arterial Blood Pressure",
            "Baroreceptor & Chemoreceptor Reflexes",
            "Cardiac Output & Frank-Starling Law",
            "Coronary Circulation Regulation",
            "Microcirculation & Capillary Exchange"
        ],
        "Respiratory System": [
            "Mechanics of Breathing & Lung Compliance",
            "Surfactant & Alveolar Surface Tension",
            "Lung Volumes and Capacities (Spirometry)",
            "Oxygen-Hemoglobin Dissociation Curve",
            "Ventilation-Perfusion (V/Q) Ratio",
            "Neural & Chemical Regulation of Respiration",
            "Hypoxia Types & High Altitude Physiology"
        ],
        "Renal System": [
            "Glomerular Filtration Rate (GFR) & Autoregulation",
            "Countercurrent Mechanism & Urine Concentration",
            "Renin-Angiotensin-Aldosterone System (RAAS)",
            "Renal Regulation of Acid-Base Balance",
            "Tubular Reabsorption & Clearance",
            "Micturition Reflex"
        ],
        "Gastrointestinal System": [
            "Gastric Acid Secretion & Regulation (Proton Pump)",
            "Pancreatic Juice & Bile Secretion",
            "Intestinal Motility & Peristalsis",
            "Digestion & Absorption of Nutrients"
        ],
        "Endocrine System": [
            "Thyroid Hormone Synthesis & Regulation",
            "Insulin, Glucagon & Blood Glucose Regulation",
            "Adrenal Cortex & Stress Response",
            "Calcium Homeostasis (PTH, Calcitonin, Vit D)",
            "Anterior Pituitary Hormones & Hypothalamic Control"
        ],
        "Central Nervous System": [
            "Sensory Pathways & Receptors",
            "Pain Pathways & Gate Control Theory",
            "Motor Systems (Pyramidal & Extrapyramidal)",
            "Basal Ganglia Circuitry & Parkinsonism",
            "Cerebellum & Coordination of Movement",
            "Limbic System & Autonomic Regulation"
        ],
        "Special Senses": [
            "Optics of Vision & Phototransduction",
            "Auditory Mechanism & Organ of Corti",
            "Vestibular Apparatus & Equilibrium",
            "Olfactory & Taste Pathways"
        ]
    },
    "biochemistry": {
        "Cell & Biomolecules": [
            "Amino Acid Properties & Classification",
            "Protein Structure (Primary, Secondary, Tertiary)",
            "Lipid Classification & Membrane Structure",
            "Nucleotide Chemistry"
        ],
        "Enzymes": [
            "Enzyme Kinetics & Michaelis-Menten Equation",
            "Enzyme Inhibition (Competitive vs Non-competitive)",
            "Allosteric Regulation & Coenzymes",
            "Diagnostic Enzymes & Clinical Biomarkers"
        ],
        "Carbohydrate Metabolism": [
            "Glycolysis & Regulation",
            "Citric Acid (TCA) Cycle & Energetics",
            "Gluconeogenesis & Cori Cycle",
            "Glycogen Synthesis & Glycogenolysis",
            "HMP Shunt & G6PD Deficiency",
            "Blood Glucose Regulation & Diabetes Biomarkers",
            "Galactose & Fructose Metabolism"
        ],
        "Lipid Metabolism": [
            "Beta-Oxidation of Fatty Acids & Energetics",
            "Ketone Body Synthesis & Ketoacidosis",
            "Cholesterol Biosynthesis & Regulation",
            "Lipoprotein Metabolism (Chylomicrons, LDL, HDL)",
            "Fatty Liver & Atherosclerosis"
        ],
        "Protein & Amino Acid Metabolism": [
            "Urea Cycle & Hyperammonemia",
            "Transamination & Deamination",
            "Inborn Errors of Amino Acid Metabolism (PKU, Alkaptonuria)",
            "Metabolism of Glycine & Sulfur Amino Acids",
            "One-Carbon Metabolism"
        ],
        "Molecular Biology & Genetics": [
            "DNA Replication & Repair Mechanisms",
            "Transcription & Post-Transcriptional Processing",
            "Translation & Genetic Code",
            "Regulation of Gene Expression",
            "Recombinant DNA & Polymerase Chain Reaction (PCR)"
        ],
        "Nutrition & Vitamins": [
            "Water-Soluble Vitamins (B-Complex, Vit C)",
            "Fat-Soluble Vitamins (A, D, E, K)",
            "Mineral Metabolism (Iron, Calcium, Trace Elements)",
            "Protein Energy Malnutrition (Kwashiorkor, Marasmus)"
        ],
        "Clinical & Integrated Biochemistry": [
            "Heme Synthesis & Porphyrias",
            "Jaundice & Bilirubin Metabolism",
            "Acid-Base Balance & Anion Gap",
            "Liver Function Tests & Renal Function Tests"
        ]
    },
    "pathology": {
        "General Pathology": [
            "Cell Injury & Necrosis vs Apoptosis",
            "Cellular Adaptations (Hypertrophy, Metaplasia)",
            "Intracellular Accumulations & Calcification"
        ],
        "Inflammation & Repair": [
            "Acute & Chronic Inflammation",
            "Chemical Mediators of Inflammation",
            "Granulomatous Diseases & Tuberculosis",
            "Wound Healing & Repair Mechanisms"
        ],
        "Hemodynamics & Shock": [
            "Thrombosis, Embolism & Infarction",
            "Edema Pathophysiology",
            "Shock (Hypovolemic, Septic, Cardiogenic)"
        ],
        "Neoplasia": [
            "Neoplasia (Oncogenes, Tumor Suppressors & Metastasis)",
            "Benign vs Malignant Characteristics",
            "Carcinogenesis & Tumor Markers",
            "Tumor Staging & Grading (TNM)"
        ],
        "Hematology": [
            "Iron Deficiency & Megaloblastic Anemias",
            "Hemolytic Anemias & Sickle Cell/Thalassemia",
            "Leukemias (ALL, AML, CML, CLL)",
            "Lymphomas (Hodgkin vs Non-Hodgkin)",
            "Coagulation Disorders & Thrombocytopenia"
        ],
        "Cardiovascular Pathology": [
            "Atherosclerosis & Ischemic Heart Disease",
            "Heart Failure (Pathophysiology & Morphology)",
            "Rheumatic Heart Disease & Endocarditis",
            "Hypertension & Cardiomyopathy"
        ],
        "Respiratory Pathology": [
            "COPD (Emphysema, Chronic Bronchitis)",
            "Bronchial Asthma & Bronchiectasis",
            "Pneumonia Types & Pulmonary Tuberculosis",
            "Lung Tumors & Morphology"
        ],
        "Renal Pathology": [
            "Glomerulonephritis & Nephrotic Syndrome",
            "Acute Tubular Necrosis & Renal Failure",
            "Pyelonephritis & Renal Cell Carcinoma"
        ],
        "Gastrointestinal & Hepatobiliary": [
            "Peptic Ulcer Disease & Gastric Carcinoma",
            "Inflammatory Bowel Disease (Crohn's vs UC)",
            "Cirrhosis & Chronic Viral Hepatitis",
            "Gallstones & Pancreatitis Pathology"
        ]
    },
    "pharmacology": {
        "General Pharmacology": [
            "Pharmacokinetics (Absorption, Distribution, Metabolism, Clearance)",
            "Pharmacodynamics & Receptor Mechanics",
            "Adverse Drug Reactions & Drug Toxicity"
        ],
        "Autonomic Nervous System": [
            "Cholinergic & Anticholinergic Drugs",
            "Adrenergic Agonists & Sympathomimetics",
            "Alpha & Beta Blockers",
            "Drugs for Glaucoma & Myasthenia Gravis"
        ],
        "Cardiovascular & Renal": [
            "Antihypertensive Drugs (ACEI, ARBs, CCBs)",
            "Drugs for Heart Failure (Digoxin, ARNi, SGLT2i)",
            "Antianginal Drugs & Nitrates",
            "Antiarrhythmic Drugs",
            "Diuretics (Furosemide, Thiazides)"
        ],
        "Central Nervous System": [
            "Sedative-Hypnotics & Benzodiazepines",
            "Antiepileptic Drugs",
            "Antidepressants & Antipsychotics",
            "Opioid Analgesics & Antagonists",
            "Drugs for Parkinson's Disease"
        ],
        "Antimicrobial & Chemotherapy": [
            "Beta-Lactam Antibiotics (Penicillins, Cephalosporins)",
            "Aminoglycosides, Macrolides & Fluoroquinolones",
            "Antitubercular Drugs (RIPE Regimen)",
            "Antifungal & Antiviral Drugs",
            "Antimalarial Drugs",
            "Anticancer Drugs (Alkylating Agents, Antimetabolites)"
        ],
        "Endocrine Pharmacology": [
            "Insulins & Oral Hypoglycemic Agents",
            "Corticosteroids & Clinical Uses",
            "Thyroid & Antithyroid Drugs",
            "Oral Contraceptives & Estrogens"
        ],
        "Autacoids & Respiratory": [
            "NSAIDs & Paracetamol",
            "Drugs for Bronchial Asthma (Inhaled Steroids, Beta Agonists)",
            "Antihistamines & H2 Blockers"
        ]
    },
    "microbiology": {
        "General Microbiology & Immunology": [
            "Bacterial Cell Wall & Gram Staining",
            "Culture Media & Sterilization Techniques",
            "Innate vs Adaptive Immunity & Vaccines",
            "Antigen-Antibody Reactions & Serology",
            "Hypersensitivity Reactions (Types I-IV)"
        ],
        "Systemic Bacteriology": [
            "Staphylococcus & Streptococcus Infections",
            "Mycobacterium tuberculosis & Leprosy",
            "Enteric Fever (Salmonella typhi)",
            "Corynebacterium diphtheriae",
            "Vibrio cholerae & Diarrheal Pathogens",
            "Clostridium (Tetanus, Gas Gangrene)"
        ],
        "Virology": [
            "Viral Hepatitis (HBV, HCV, HAV)",
            "HIV & Opportunistic Infections",
            "Dengue, Rabies & Arboviruses",
            "Influenza & Respiratory Viruses",
            "Herpesviruses (HSV, VZV, CMV)"
        ],
        "Parasitology": [
            "Malaria Parasite Life Cycle & Diagnosis",
            "Entamoeba histolytica & Giardia",
            "Leishmania donovani (Kala-Azar)",
            "Intestinal Nematodes (Ascaris, Hookworm)",
            "Cestodes (Taenia, Echinococcus)"
        ],
        "Mycology & Applied": [
            "Dermatophytes & Superficial Mycoses",
            "Opportunistic Fungi (Candida, Aspergillus, Mucor)",
            "Hospital Acquired Infections & Biomedical Waste",
            "Antimicrobial Susceptibility Testing"
        ]
    },
    "community medicine": {
        "Epidemiology": [
            "Epidemiological Study Designs (Cohort, Case-Control, RCT)",
            "Measurements of Morbidity & Mortality",
            "Screening of Disease (Sensitivity & Specificity)",
            "Investigation of an Epidemic"
        ],
        "Biostatistics": [
            "Measures of Central Tendency & Dispersion",
            "Tests of Significance (Chi-square, t-test)",
            "Sampling Methods & Normal Distribution"
        ],
        "Communicable & Non-Communicable Diseases": [
            "Tuberculosis Control (NTEP)",
            "Vector-Borne Disease Control Programs (NVBDCP)",
            "Cardiovascular Disease & Diabetes Prevention",
            "National AIDS Control Programme"
        ],
        "Maternal, Child Health & Nutrition": [
            "National Immunization Schedule",
            "Maternal & Infant Mortality Rates",
            "Antenatal & Postnatal Care Services",
            "Nutrition Assessment & Malnutrition Programs"
        ],
        "Health Programs & Environment": [
            "Primary Health Care & Ayushman Bharat",
            "Water Purification & Sanitation Methods",
            "Solid Waste Management & Occupational Health"
        ]
    },
    "forensic medicine": {
        "Thanatology": [
            "Signs of Death & Rigor Mortis",
            "Post-Mortem Changes & Decomposition",
            "Estimation of Time Since Death"
        ],
        "Mechanical Injuries": [
            "Abrasions, Contusions, Lacerations & Incised Wounds",
            "Firearm Injuries & Ballistics",
            "Head Injury & Intracranial Hemorrhages"
        ],
        "Asphyxial Deaths": [
            "Hanging vs Strangulation Differences",
            "Drowning Mechanics & Diatom Test",
            "Suffocation & Choking"
        ],
        "Forensic Toxicology": [
            "Organophosphate & Carbamate Poisoning",
            "Snakebite Envenomation & Management",
            "Corrosive & Heavy Metal Poisoning",
            "Alcohol Poisoning & Medico-Legal Aspects"
        ],
        "Medical Jurisprudence": [
            "Medical Ethics & Informed Consent",
            "Medical Negligence & Legal Proceedings",
            "Medico-Legal Autopsy Procedures"
        ]
    },
    "general medicine": {
        "Cardiovascular": [
            "Heart Failure Classifications & Clinical Management",
            "Acute Coronary Syndrome (STEMI vs NSTEMI)",
            "Hypertension & Hypertensive Crisis",
            "Valvular Heart Disease & Infective Endocarditis",
            "Arrhythmias & Cardiac Arrest Management"
        ],
        "Respiratory": [
            "Pneumonia & Sepsis Management",
            "Chronic Obstructive Pulmonary Disease (COPD)",
            "Bronchial Asthma & Acute Exacerbation",
            "Tuberculosis Clinical Management & ATT"
        ],
        "Gastroenterology & Hepatology": [
            "Upper Gastrointestinal Bleeding Management",
            "Cirrhosis, Portal Hypertension & Ascites",
            "Acute Pancreatitis Evaluation"
        ],
        "Nephrology & Endocrinology": [
            "Acute Kidney Injury & Chronic Kidney Disease",
            "Type 2 Diabetes Mellitus & Diabetic Ketoacidosis",
            "Thyroid Disorders & Crisis"
        ],
        "Neurology & Infectious": [
            "Stroke Management (Ischemic vs Hemorrhagic)",
            "Meningitis & Encephalitis",
            "Enteric Fever, Malaria & Dengue Clinical Protocols"
        ]
    },
    "general surgery": {
        "General Principles": [
            "Shock, Hemorrhage & Fluid Resuscitation",
            "Surgical Site Infections & Asepsis",
            "Burns Assessment & Parkland Formula",
            "Wound Healing & Management"
        ],
        "Abdominal Surgery": [
            "Acute Appendicitis & Peritonitis",
            "Inguinal & Femoral Hernias Management",
            "Intestinal Obstruction",
            "Gallstone Disease & Cholecystectomy"
        ],
        "Endocrine & Breast": [
            "Thyroid Swellings & Surgical Evaluation",
            "Breast Lump Assessment & Carcinoma Staging"
        ],
        "Urology & Vascular": [
            "Urolithiasis & Hematuria Evaluation",
            "Benign Prostatic Hyperplasia",
            "Varicose Veins & Peripheral Vascular Disease"
        ]
    },
    "obstetrics & gynaecology": {
        "Obstetrics": [
            "Antenatal Care & Normal Labor Stages",
            "Pre-eclampsia & Eclampsia Protocols",
            "Postpartum Hemorrhage (PPH) Management",
            "Antepartum Hemorrhage (Placenta Previa)",
            "Fetal Distress & Operative Delivery"
        ],
        "Gynaecology": [
            "Abnormal Uterine Bleeding (PALM-COEIN)",
            "Cervical Cancer Screening (Pap Smear & HPV)",
            "Fibroids & Endometriosis",
            "Polycystic Ovarian Syndrome (PCOS)",
            "Contraceptive Methods & Family Planning"
        ]
    },
    "pediatrics": {
        "Development & Nutrition": [
            "Developmental Milestones (Motor, Language, Social)",
            "Protein Energy Malnutrition (PEM)",
            "Infant Nutrition & Breastfeeding"
        ],
        "Neonatology": [
            "Neonatal Resuscitation Protocol",
            "Neonatal Jaundice & Phototherapy",
            "Respiratory Distress in Newborn"
        ],
        "Systemic Pediatrics": [
            "Acute Diarrhea & Dehydration Management",
            "Childhood Immunization & Vaccine Protocols",
            "Pediatric Pneumonia & Asthma",
            "Congenital Heart Diseases in Children"
        ]
    },
    "ophthalmology": {
        "Lens & Cornea": [
            "Cataract Types & Surgical Techniques",
            "Corneal Ulcers & Keratitis",
            "Conjunctivitis Types"
        ],
        "Glaucoma & Retina": [
            "Glaucoma (Open Angle vs Angle Closure)",
            "Diabetic Retinopathy & Retinal Detachment",
            "Refractive Errors & Amblyopia"
        ]
    },
    "ent": {
        "Ear": [
            "Acute & Chronic Otitis Media (CSOM)",
            "Hearing Loss & Tuning Fork Tests",
            "Vertigo & Meniere's Disease"
        ],
        "Nose & Throat": [
            "Epistaxis & Deviated Nasal Septum",
            "Sinusitis & Nasal Polyps",
            "Tonsillitis & Adenoid Hypertrophy",
            "Hoarseness & Stridor Evaluation"
        ]
    }
}

# Flattened catalog for backward compatibility
CANONICAL_SUBJECT_TOPICS: Dict[str, List[str]] = {
    subj: [t for unit_topics in units.values() for t in unit_topics]
    for subj, units in CANONICAL_CURRICULUM_SYLLABUS.items()
}

# Domain keyword associations for subject-topic validation
TOPIC_DOMAIN_ASSOCIATIONS: List[Tuple[re.Pattern, str, str]] = [
    # (Pattern, Primary Subject, Display Name)
    (re.compile(r"\b(heart failure|congestive heart failure|chf|shock|cardiogenic shock|septic shock|atherosclerosis|infarction|necrosis|thrombosis|embolism|neoplasia|tumor suppressor|oncogene)\b", re.I), "pathology", "Pathology / Medicine"),
    (re.compile(r"\b(brachial plexus|axillary|femoral triangle|inguinal canal|cubital fossa|popliteal|cranial nerve|triangle of neck|carpal tunnel|rotator cuff|meniscus|sciatica|radius|ulna|humerus|tibia|fibula|sacrum|foramen|anastomosis|histology of)\b", re.I), "anatomy", "Anatomy"),
    (re.compile(r"\b(cardiac cycle|pressure-volume|ecg|action potential|resting membrane|gfr|glomerular filtration|countercurrent|raas|renin-angiotensin|lung volume|compliance|baroreceptor|synapse|neuromuscular junction|myasthenia|surfactant)\b", re.I), "physiology", "Physiology"),
    (re.compile(r"\b(glycolysis|tca cycle|krebs|gluconeogenesis|beta-oxidation|hmp shunt|urea cycle|phenylketonuria|pku|enzyme kinetics|michaelis-menten|transcription|translation|dna replication|porphyria|hyperammonemia)\b", re.I), "biochemistry", "Biochemistry"),
    (re.compile(r"\b(pharmacokinetics|pharmacodynamics|bioavailability|beta blocker|ace inhibitor|furosemide|digoxin|penicillin|cephalosporin|aminoglycoside|nsaid|opioid|adverse drug|receptor antagonist)\b", re.I), "pharmacology", "Pharmacology"),
    (re.compile(r"\b(salmonella|staphylococcus|streptococcus|tuberculosis bacillus|mycobacterium|hbv|hcv|hiv|plasmodium|malaria|culture media|gram stain|antigen-antibody|hypersensitivity)\b", re.I), "microbiology", "Microbiology"),
    (re.compile(r"\b(rigor mortis|thanatology|post-mortem|hanging|strangulation|drowning|organophosphate|autopsy|firearm wound|medical jurisprudence)\b", re.I), "forensic medicine", "Forensic Medicine (FMT)"),
    (re.compile(r"\b(epidemiology|cohort study|case-control|p-value|chi-square|vaccine schedule|maternal mortality|infant mortality|sanitation|water purification)\b", re.I), "community medicine", "Community Medicine (PSM)"),
]


def resolve_subject_key(name: str, code: str = "") -> Optional[str]:
    """Finds canonical subject key from name or code."""
    n = (name or "").lower().strip()
    c = (code or "").lower().strip()
    target = f"{n} {c}"
    
    for k in CANONICAL_SUBJECT_TOPICS.keys():
        if k in target:
            return k
    
    # Aliases
    aliases = {
        "anat": "anatomy",
        "phys": "physiology",
        "biochem": "biochemistry",
        "path": "pathology",
        "pharm": "pharmacology",
        "micro": "microbiology",
        "fmt": "forensic medicine",
        "forensic": "forensic medicine",
        "psm": "community medicine",
        "spm": "community medicine",
        "med": "general medicine",
        "medicine": "general medicine",
        "internal medicine": "general medicine",
        "surg": "general surgery",
        "surgery": "general surgery",
        "obg": "obstetrics & gynaecology",
        "obgyn": "obstetrics & gynaecology",
        "obs": "obstetrics & gynaecology",
        "gynaec": "obstetrics & gynaecology",
        "ped": "pediatrics",
        "paed": "pediatrics",
        "paediatrics": "pediatrics"
    }
    for alias, canonical in aliases.items():
        if alias in n or (c and alias in c):
            return canonical
            
    return None


def match_portion_key(portions: Dict[str, List[str]], query: str) -> Optional[str]:
    """Finds matching syllabus portion/unit name from a query string."""
    q = (query or "").lower().strip()
    if not q or q in ["all", "all units", "whole subject", "entire syllabus"]:
        return None

    # Exact match
    for p in portions.keys():
        if p.lower() == q:
            return p

    # Substring match
    for p in portions.keys():
        if q in p.lower() or p.lower() in q:
            return p

    # Token match
    tokens = [w for w in re.split(r"[\s&/,]+", q) if len(w) >= 3]
    if tokens:
        for p in portions.keys():
            p_lower = p.lower()
            if any(t in p_lower for t in tokens):
                return p

    return None


async def get_subject_topic_suggestions(
    db: AsyncSession,
    user_id: str,
    subject_id: str,
    subject_name: str,
    portion: Optional[str] = None,
    year_of_study: Optional[str] = None,
    days_remaining: Optional[int] = None,
    target_score: Optional[float] = None
) -> Dict[str, Any]:
    """
    Returns dynamic, subject-aware and portion-scoped topic suggestions for an exam
    using a HYBRID architecture:
    1. MedPilot's structured curriculum (CANONICAL_CURRICULUM_SYLLABUS) is the authoritative primary source.
    2. Uses ExamSyllabusAIService for deterministic & AI-assisted portion matching with confidence tiers.
    3. If confidence is 'low', guidance prompt is returned without hallucinated topics.
    4. Incorporates student's recorded lecture topics for this subject (ClassTopic).
    5. Incorporates previous exam topics for this subject.
    6. Strictly discards any cross-subject leakage (e.g. Heart failure in Anatomy).
    7. Contextually ranks verified topics using AI / academic rules.
    """
    subject_key = resolve_subject_key(subject_name)
    subject_portions = CANONICAL_CURRICULUM_SYLLABUS.get(subject_key, {}) if subject_key else {}
    available_portions = list(subject_portions.keys())

    matched_portion: Optional[str] = None
    confidence: Optional[str] = None
    confidence_score: Optional[float] = None
    match_message: Optional[str] = None
    ai_assisted: bool = False

    if portion:
        match_res = await ExamSyllabusAIService.match_portion_hybrid(
            subject_name=subject_name,
            subject_key=subject_key,
            query=portion,
            available_portions=available_portions
        )
        matched_portion = match_res.get("matched_portion")
        confidence = match_res.get("confidence")
        confidence_score = match_res.get("confidence_score")
        match_message = match_res.get("match_message")
        ai_assisted = match_res.get("ai_assisted", False)

        # If low confidence, do not load irrelevant topics; prompt student
        if confidence == "low" and not matched_portion:
            return {
                "suggestions": [],
                "available_portions": available_portions,
                "portion": portion,
                "matched_portion": None,
                "confidence": "low",
                "confidence_score": confidence_score or 0.2,
                "match_message": match_message or "We couldn't confidently match this portion to the syllabus. Add topics manually or choose a syllabus unit.",
                "ai_ranked": False,
                "ai_provider": ExamSyllabusAIService.get_configured_provider_name()
            }

    suggestions: List[str] = []
    seen = set()

    def add_topic(t: str):
        cleaned = t.strip()
        if not cleaned:
            return
        # Ignore literal outdated placeholder
        if "cardiovascular system, heart failure, shock" in cleaned.lower():
            return
        # Ensure zero cross-subject leakage (e.g. Heart failure in Anatomy)
        if subject_key:
            val = validate_topic_for_subject(cleaned, subject_name)
            if not val["is_valid"]:
                return
        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            suggestions.append(cleaned)

    # 1. User's recorded lecture topics for this subject (prioritized first)
    stmt_topics = (
        select(ClassTopic.title)
        .join(ClassOccurrence, ClassTopic.occurrence_id == ClassOccurrence.id)
        .filter(
            ClassOccurrence.user_id == user_id,
            ClassOccurrence.subject_id == subject_id,
            ClassOccurrence.is_archived == False
        )
        .order_by(ClassOccurrence.date.desc())
    )
    db_topics = (await db.execute(stmt_topics)).scalars().all()
    for t in db_topics:
        if t and t.strip():
            # If portion is specified, check if class topic relates to portion
            if matched_portion or portion:
                active_p = matched_portion or portion
                pq_tokens = [w.lower() for w in re.split(r"[\s&/,]+", active_p) if len(w) >= 3]
                if any(tok in t.lower() for tok in pq_tokens):
                    add_topic(t.strip())
            else:
                add_topic(t.strip())

    # 2. Topics from previous exams for this subject
    stmt_exams = (
        select(Exam.important_topics, Exam.syllabus_portion)
        .filter(Exam.user_id == user_id, Exam.subject_id == subject_id)
    )
    prev_exams = (await db.execute(stmt_exams)).all()
    for top_list, ex_portion in prev_exams:
        if isinstance(top_list, list):
            for t in top_list:
                if isinstance(t, str):
                    if matched_portion or portion:
                        active_p = matched_portion or portion
                        if ex_portion and active_p.lower() in ex_portion.lower():
                            add_topic(t)
                        else:
                            pq_tokens = [w.lower() for w in re.split(r"[\s&/,]+", active_p) if len(w) >= 3]
                            if any(tok in t.lower() for tok in pq_tokens):
                                add_topic(t)
                    else:
                        add_topic(t)

    # 3. Canonical verified syllabus topics for the matched portion or entire subject
    if matched_portion and matched_portion in subject_portions:
        portion_topics = subject_portions[matched_portion]
        for ct in portion_topics:
            add_topic(ct)
    elif portion and not matched_portion:
        pq_tokens = [w.lower() for w in re.split(r"[\s&/,]+", portion) if len(w) >= 3]
        all_canonical = [t for unit_topics in subject_portions.values() for t in unit_topics]
        for ct in all_canonical:
            if any(tok in ct.lower() for tok in pq_tokens):
                add_topic(ct)
    else:
        # No portion specified: provide top high-yield topics across portions of this subject
        for unit_name, unit_topics in subject_portions.items():
            for ct in unit_topics[:3]:
                add_topic(ct)
        for unit_name, unit_topics in subject_portions.items():
            for ct in unit_topics[3:]:
                add_topic(ct)

    # 4. Fetch context for ranking (missed topics & feedback)
    missed_topics: List[str] = []
    try:
        missed_stmt = (
            select(ClassTopic.title)
            .join(ClassOccurrence, ClassTopic.occurrence_id == ClassOccurrence.id)
            .join(Attendance, Attendance.occurrence_id == ClassOccurrence.id)
            .filter(
                ClassOccurrence.user_id == user_id,
                ClassOccurrence.subject_id == subject_id,
                Attendance.status == "absent"
            )
        )
        missed_topics = list((await db.execute(missed_stmt)).scalars().all())
    except Exception as e:
        logger.debug(f"Failed to query missed topics for ranking: {e}")

    flagged_feedback_topics: List[str] = []
    try:
        feedback_stmt = (
            select(StudyTask.title, StudyTask.topic_name)
            .filter(
                StudyTask.user_id == user_id,
                StudyTask.subject_id == subject_id,
                StudyTask.feedback.in_(["hard", "need_more_time"])
            )
        )
        fb_rows = (await db.execute(feedback_stmt)).all()
        for r in fb_rows:
            if r[0]:
                flagged_feedback_topics.append(r[0])
            if r[1]:
                flagged_feedback_topics.append(r[1])
    except Exception as e:
        logger.debug(f"Failed to query feedback topics for ranking: {e}")

    # 5. Hybrid AI / Academic Context Ranking
    ranked_suggestions, ai_ranked = await ExamSyllabusAIService.rank_verified_topics_hybrid(
        verified_topics=suggestions,
        subject_name=subject_name,
        portion_name=matched_portion or portion,
        days_remaining=days_remaining,
        target_score=target_score,
        missed_topics=missed_topics,
        flagged_feedback_topics=flagged_feedback_topics
    )

    return {
        "suggestions": ranked_suggestions,
        "available_portions": available_portions,
        "portion": matched_portion or portion,
        "matched_portion": matched_portion,
        "confidence": confidence,
        "confidence_score": confidence_score,
        "match_message": match_message,
        "ai_ranked": ai_ranked,
        "ai_provider": ExamSyllabusAIService.get_configured_provider_name()
    }


def validate_topic_for_subject(
    topic: str,
    subject_name: str,
    subject_code: str = ""
) -> dict:
    """
    Validates if a topic belongs to the selected subject.
    Detects cross-subject mismatches and generates a gentle non-blocking prompt:
    "This topic may not belong to the selected subject. Add anyway?"
    """
    t_clean = (topic or "").strip()
    s_clean = (subject_name or "").strip()
    if not t_clean or not s_clean:
        return {"is_valid": True, "warning": None, "suggested_subject": None}

    current_subj_key = resolve_subject_key(s_clean, subject_code)

    # Check against known domain keyword patterns
    for pattern, expected_subj, display_name in TOPIC_DOMAIN_ASSOCIATIONS:
        if pattern.search(t_clean):
            if current_subj_key and current_subj_key != expected_subj:
                # If current subject is different, verify it's not a shared concept
                # e.g., "Thorax & Coronary Circulation" is legitimate Anatomy, but "Heart Failure" is not
                if expected_subj in ("pathology", "general medicine") and current_subj_key == "anatomy":
                    if any(w in t_clean.lower() for w in ["failure", "shock", "infarction", "atherosclerosis"]):
                        return {
                            "is_valid": False,
                            "suggested_subject": display_name,
                            "warning": f"'{t_clean}' typically belongs to {display_name}. This topic may not belong to the selected subject. Add anyway?"
                        }
                elif expected_subj == "biochemistry" and current_subj_key in ("anatomy", "general surgery", "forensic medicine"):
                    return {
                        "is_valid": False,
                        "suggested_subject": display_name,
                        "warning": f"'{t_clean}' typically belongs to {display_name}. This topic may not belong to the selected subject. Add anyway?"
                    }
                elif expected_subj == "anatomy" and current_subj_key in ("biochemistry", "community medicine"):
                    return {
                        "is_valid": False,
                        "suggested_subject": display_name,
                        "warning": f"'{t_clean}' typically belongs to {display_name}. This topic may not belong to the selected subject. Add anyway?"
                    }
                elif expected_subj == "physiology" and current_subj_key in ("anatomy", "biochemistry"):
                    if any(w in t_clean.lower() for w in ["action potential", "cardiac cycle", "ecg", "gfr", "raas"]):
                        return {
                            "is_valid": False,
                            "suggested_subject": display_name,
                            "warning": f"'{t_clean}' typically belongs to {display_name}. This topic may not belong to the selected subject. Add anyway?"
                        }

    return {"is_valid": True, "warning": None, "suggested_subject": None}
