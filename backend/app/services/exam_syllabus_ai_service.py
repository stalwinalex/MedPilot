import re
import json
import logging
from typing import List, Dict, Optional, Tuple, Any
from app.agent.llm_provider import get_llm_provider, is_gemini_configured, is_groq_configured, is_openai_configured

logger = logging.getLogger(__name__)

# Medical portion aliases mapping common vernacular / clinical terms to canonical syllabus units
MEDICAL_PORTION_ALIASES: Dict[str, Dict[str, str]] = {
    "anatomy": {
        "upper extremity": "Upper Limb",
        "upper extremity nerves": "Upper Limb",
        "upper limb nerves": "Upper Limb",
        "arm": "Upper Limb",
        "forearm": "Upper Limb",
        "hand": "Upper Limb",
        "shoulder": "Upper Limb",
        "brachial": "Upper Limb",
        "cubital": "Upper Limb",
        "carpal": "Upper Limb",
        "pectoral": "Upper Limb",
        "axilla": "Upper Limb",
        "lower extremity": "Lower Limb",
        "leg": "Lower Limb",
        "thigh": "Lower Limb",
        "foot": "Lower Limb",
        "hip": "Lower Limb",
        "knee": "Lower Limb",
        "femur": "Lower Limb",
        "femoral": "Lower Limb",
        "popliteal": "Lower Limb",
        "gluteal": "Lower Limb",
        "sciatic": "Lower Limb",
        "chest": "Thorax",
        "lungs": "Thorax",
        "heart": "Thorax",
        "cardiac": "Thorax",
        "mediastinum": "Thorax",
        "pleura": "Thorax",
        "ribs": "Thorax",
        "intercostal": "Thorax",
        "belly": "Abdomen & Pelvis",
        "abdomen": "Abdomen & Pelvis",
        "pelvis": "Abdomen & Pelvis",
        "peritoneum": "Abdomen & Pelvis",
        "stomach": "Abdomen & Pelvis",
        "liver": "Abdomen & Pelvis",
        "kidney": "Abdomen & Pelvis",
        "inguinal": "Abdomen & Pelvis",
        "hernia": "Abdomen & Pelvis",
        "head": "Head & Neck",
        "neck": "Head & Neck",
        "face": "Head & Neck",
        "cranial nerves": "Head & Neck",
        "thyroid": "Head & Neck",
        "parotid": "Head & Neck",
        "carotid": "Head & Neck",
        "pharynx": "Head & Neck",
        "larynx": "Head & Neck",
        "brain": "Neuroanatomy",
        "cns": "Neuroanatomy",
        "spinal cord": "Neuroanatomy",
        "brainstem": "Neuroanatomy",
        "cerebrum": "Neuroanatomy",
        "cerebellum": "Neuroanatomy",
        "ventricles": "Neuroanatomy",
        "csf": "Neuroanatomy",
        "meninges": "Neuroanatomy",
        "tissues": "Histology",
        "microscopic anatomy": "Histology",
        "epithelium": "Histology",
        "development": "Embryology",
        "fetus": "Embryology",
        "congenital": "Embryology",
        "pharyngeal arches": "Embryology",
        "general": "General Anatomy",
        "bones": "General Anatomy",
        "joints": "General Anatomy",
        "connective tissue": "General Anatomy"
    },
    "physiology": {
        "heart": "Cardiovascular System",
        "cvs": "Cardiovascular System",
        "cardio": "Cardiovascular System",
        "circulation": "Cardiovascular System",
        "blood pressure": "Cardiovascular System",
        "ecg": "Cardiovascular System",
        "cardiac cycle": "Cardiovascular System",
        "lungs": "Respiratory System",
        "pulmonary": "Respiratory System",
        "respiratory": "Respiratory System",
        "breathing": "Respiratory System",
        "ventilation": "Respiratory System",
        "spirometry": "Respiratory System",
        "gas exchange": "Respiratory System",
        "kidney": "Renal System",
        "renal": "Renal System",
        "nephron": "Renal System",
        "gfr": "Renal System",
        "urine": "Renal System",
        "micturition": "Renal System",
        "gut": "Gastrointestinal System",
        "git": "Gastrointestinal System",
        "stomach": "Gastrointestinal System",
        "digestion": "Gastrointestinal System",
        "absorption": "Gastrointestinal System",
        "peristalsis": "Gastrointestinal System",
        "hormones": "Endocrine System",
        "endocrine": "Endocrine System",
        "thyroid": "Endocrine System",
        "insulin": "Endocrine System",
        "pituitary": "Endocrine System",
        "adrenal": "Endocrine System",
        "brain": "Central Nervous System",
        "cns": "Central Nervous System",
        "sensory": "Central Nervous System",
        "motor": "Central Nervous System",
        "reflex": "Central Nervous System",
        "nerve": "Nerve & Muscle",
        "muscle": "Nerve & Muscle",
        "action potential": "Nerve & Muscle",
        "synapse": "Nerve & Muscle",
        "nmj": "Nerve & Muscle",
        "rbc": "Blood",
        "wbc": "Blood",
        "platelets": "Blood",
        "clotting": "Blood",
        "hemostasis": "Blood",
        "anemia": "Blood",
        "eye": "Special Senses",
        "ear": "Special Senses",
        "vision": "Special Senses",
        "hearing": "Special Senses"
    },
    "biochemistry": {
        "carbohydrate": "Carbohydrate Metabolism",
        "carbs": "Carbohydrate Metabolism",
        "glucose": "Carbohydrate Metabolism",
        "glycolysis": "Carbohydrate Metabolism",
        "tca": "Carbohydrate Metabolism",
        "krebs": "Carbohydrate Metabolism",
        "gluconeogenesis": "Carbohydrate Metabolism",
        "glycogen": "Carbohydrate Metabolism",
        "lipids": "Lipid Metabolism",
        "fat": "Lipid Metabolism",
        "fatty acid": "Lipid Metabolism",
        "cholesterol": "Lipid Metabolism",
        "lipoproteins": "Lipid Metabolism",
        "beta oxidation": "Lipid Metabolism",
        "proteins": "Protein & Amino Acid Metabolism",
        "amino acids": "Protein & Amino Acid Metabolism",
        "urea cycle": "Protein & Amino Acid Metabolism",
        "dna": "Molecular Biology & Genetics",
        "rna": "Molecular Biology & Genetics",
        "genetics": "Molecular Biology & Genetics",
        "replication": "Molecular Biology & Genetics",
        "transcription": "Molecular Biology & Genetics",
        "translation": "Molecular Biology & Genetics",
        "pcr": "Molecular Biology & Genetics",
        "vitamins": "Vitamins & Minerals",
        "minerals": "Vitamins & Minerals",
        "iron": "Vitamins & Minerals",
        "calcium": "Vitamins & Minerals",
        "enzymes": "Enzymology & Bioenergetics",
        "kinetics": "Enzymology & Bioenergetics",
        "bioenergetics": "Enzymology & Bioenergetics",
        "etc": "Enzymology & Bioenergetics",
        "nutrition": "Nutrition & Energy Balance"
    },
    "pathology": {
        "general": "General Pathology",
        "cell injury": "General Pathology",
        "inflammation": "General Pathology",
        "necrosis": "General Pathology",
        "neoplasia": "General Pathology",
        "tumors": "General Pathology",
        "cancer": "General Pathology",
        "blood": "Hematology",
        "anemia": "Hematology",
        "leukemia": "Hematology",
        "heart": "Cardiovascular Pathology",
        "infarction": "Cardiovascular Pathology",
        "atherosclerosis": "Cardiovascular Pathology",
        "lungs": "Respiratory Pathology",
        "pneumonia": "Respiratory Pathology",
        "tb": "Respiratory Pathology",
        "kidney": "Renal Pathology",
        "nephritis": "Renal Pathology",
        "glomerulonephritis": "Renal Pathology",
        "git": "Gastrointestinal Pathology",
        "liver": "Gastrointestinal Pathology",
        "cirrhosis": "Gastrointestinal Pathology"
    },
    "pharmacology": {
        "general": "General Pharmacology",
        "pharmacokinetics": "General Pharmacology",
        "pharmacodynamics": "General Pharmacology",
        "ans": "Autonomic Nervous System",
        "autonomic": "Autonomic Nervous System",
        "cholinergic": "Autonomic Nervous System",
        "adrenergic": "Autonomic Nervous System",
        "cvs": "Cardiovascular Pharmacology",
        "hypertension": "Cardiovascular Pharmacology",
        "heart failure": "Cardiovascular Pharmacology",
        "antiarrhythmics": "Cardiovascular Pharmacology",
        "antimicrobials": "Chemotherapy & Antimicrobials",
        "antibiotics": "Chemotherapy & Antimicrobials",
        "penicillin": "Chemotherapy & Antimicrobials",
        "antifungal": "Chemotherapy & Antimicrobials",
        "antiviral": "Chemotherapy & Antimicrobials",
        "cns": "Central Nervous System Pharmacology",
        "sedatives": "Central Nervous System Pharmacology",
        "antidepressants": "Central Nervous System Pharmacology",
        "analgesics": "Autacoids & NSAIDs",
        "nsaids": "Autacoids & NSAIDs",
        "pain": "Autacoids & NSAIDs"
    },
    "microbiology": {
        "general": "General Bacteriology & Immunology",
        "bacteriology": "General Bacteriology & Immunology",
        "immunology": "General Bacteriology & Immunology",
        "staining": "General Bacteriology & Immunology",
        "culture": "General Bacteriology & Immunology",
        "systemic bacteria": "Systemic Bacteriology",
        "bacteria": "Systemic Bacteriology",
        "staph": "Systemic Bacteriology",
        "strep": "Systemic Bacteriology",
        "salmonella": "Systemic Bacteriology",
        "tb": "Systemic Bacteriology",
        "viruses": "Virology",
        "virology": "Virology",
        "hiv": "Virology",
        "hepatitis": "Virology",
        "influenza": "Virology",
        "parasites": "Parasitology",
        "malaria": "Parasitology",
        "amoeba": "Parasitology",
        "fungus": "Mycology",
        "mycology": "Mycology",
        "candida": "Mycology"
    }
}


class ExamSyllabusAIService:
    """
    Hybrid Syllabus & Topic Service:
    - Structured MedPilot Curriculum is the authoritative primary source of truth.
    - AI is utilized strictly for understanding custom wording / ambiguous portions
      and ranking verified syllabus topics based on academic context.
    - Full fallback to deterministic fuzzy/alias matching when offline or without API keys.
    """

    @classmethod
    def is_ai_enabled(cls) -> bool:
        return is_gemini_configured() or is_groq_configured() or is_openai_configured()

    @classmethod
    def get_configured_provider_name(cls) -> str:
        if is_gemini_configured():
            return "gemini"
        if is_groq_configured():
            return "groq"
        if is_openai_configured():
            return "openai"
        return "deterministic_offline"

    @classmethod
    async def match_portion_hybrid(
        cls,
        subject_name: str,
        subject_key: Optional[str],
        query: str,
        available_portions: List[str]
    ) -> Dict[str, Any]:
        """
        Matches a user's portion query using hybrid architecture:
        1. Exact match against available syllabus units -> High confidence.
        2. Alias dictionary matching -> High confidence.
        3. Token / fuzzy local overlap -> High or Medium confidence.
        4. If uncertain and AI is enabled, calls LLM ONLY to pick from candidate units.
        5. Assigns confidence:
           - 'high': direct auto-match
           - 'medium': returns 'Did you mean {portion}?'
           - 'low': returns 'We couldn't confidently match this portion to the syllabus. Add topics manually or choose a syllabus unit.'
        """
        q = (query or "").strip()
        if not q or not available_portions:
            return {
                "matched_portion": None,
                "confidence": None,
                "confidence_score": 0.0,
                "match_message": None,
                "ai_assisted": False
            }

        q_lower = q.lower()

        # Check for 'all units' or equivalent
        if q_lower in ["all", "all units", "whole subject", "entire syllabus", "full syllabus"]:
            return {
                "matched_portion": None,
                "confidence": "high",
                "confidence_score": 1.0,
                "match_message": None,
                "ai_assisted": False
            }

        # -------------------------------------------------------------
        # 1. Exact match (Case-insensitive)
        # -------------------------------------------------------------
        for p in available_portions:
            if p.lower() == q_lower:
                return {
                    "matched_portion": p,
                    "confidence": "high",
                    "confidence_score": 1.0,
                    "match_message": None,
                    "ai_assisted": False
                }

        # -------------------------------------------------------------
        # 2. Medical Alias Dictionary Match
        # -------------------------------------------------------------
        s_key = subject_key or subject_name.lower()
        alias_map = MEDICAL_PORTION_ALIASES.get(s_key, {})
        if not alias_map:
            for k, v in MEDICAL_PORTION_ALIASES.items():
                if k in s_key or s_key in k:
                    alias_map = v
                    break

        if alias_map:
            # Check full query match in alias map
            if q_lower in alias_map:
                target_unit = alias_map[q_lower]
                if target_unit in available_portions:
                    return {
                        "matched_portion": target_unit,
                        "confidence": "high",
                        "confidence_score": 0.95,
                        "match_message": None,
                        "ai_assisted": False
                    }

            # Check constituent medical keywords in alias map
            matched_alias_units = set()
            for alias_phrase, target_unit in alias_map.items():
                if target_unit in available_portions:
                    # check if phrase is contained in user query or vice versa
                    if alias_phrase in q_lower or (len(alias_phrase) >= 4 and alias_phrase in q_lower.split()):
                        matched_alias_units.add(target_unit)

            if len(matched_alias_units) == 1:
                target_unit = list(matched_alias_units)[0]
                return {
                    "matched_portion": target_unit,
                    "confidence": "high",
                    "confidence_score": 0.90,
                    "match_message": None,
                    "ai_assisted": False
                }
            elif len(matched_alias_units) > 1:
                # Ambiguous alias (e.g. matched Upper Limb and Lower Limb)
                # Pick the one with longest match or candidate for medium confidence
                candidates = list(matched_alias_units)
                return {
                    "matched_portion": candidates[0],
                    "confidence": "medium",
                    "confidence_score": 0.65,
                    "match_message": f"Did you mean {candidates[0]}?",
                    "ai_assisted": False
                }

        # -------------------------------------------------------------
        # 3. Deterministic Token / Substring Matching (with Stemming)
        # -------------------------------------------------------------
        def _stem(w: str) -> str:
            w_str = w.lower().strip()
            if w_str.endswith("es") and len(w_str) > 4:
                return w_str[:-2]
            if w_str.endswith("s") and len(w_str) > 3:
                return w_str[:-1]
            return w_str

        q_raw_tokens = [w for w in re.split(r"[\s&/,]+", q_lower) if len(w) >= 3]
        q_tokens = set(q_raw_tokens + [_stem(w) for w in q_raw_tokens])
        q_stemmed = " ".join([_stem(w) for w in q_raw_tokens])

        token_scores: List[Tuple[str, float]] = []
        for p in available_portions:
            p_lower = p.lower()
            p_raw_tokens = [w for w in re.split(r"[\s&/,]+", p_lower) if len(w) >= 3]
            p_tokens = set(p_raw_tokens + [_stem(w) for w in p_raw_tokens])
            p_stemmed = " ".join([_stem(w) for w in p_raw_tokens])

            # Direct substring (raw or stemmed)
            if q_lower in p_lower or (q_stemmed and q_stemmed in p_stemmed):
                ratio = len(q_lower) / max(len(p_lower), 1)
                token_scores.append((p, 0.85 + 0.10 * ratio))
                continue
            elif p_lower in q_lower or (p_stemmed and p_stemmed in q_stemmed):
                token_scores.append((p, 0.85))
                continue

            # Token overlap
            if q_tokens and p_tokens:
                intersection = q_tokens.intersection(p_tokens)
                if intersection:
                    score = len(intersection) / len(p_tokens)
                    token_scores.append((p, round(score * 0.80, 2)))

        if token_scores:
            token_scores.sort(key=lambda x: -x[1])
            best_unit, best_score = token_scores[0]
            # If multiple portions match equally or closely (ambiguous query e.g. "limbs"), trigger medium confidence
            if len(token_scores) > 1 and abs(token_scores[0][1] - token_scores[1][1]) < 0.15:
                return {
                    "matched_portion": best_unit,
                    "confidence": "medium",
                    "confidence_score": 0.65,
                    "match_message": f"Did you mean {best_unit}?",
                    "ai_assisted": False
                }
            if best_score >= 0.80:
                return {
                    "matched_portion": best_unit,
                    "confidence": "high",
                    "confidence_score": best_score,
                    "match_message": None,
                    "ai_assisted": False
                }

        # -------------------------------------------------------------
        # 4. AI-Assisted Matching (Provider Abstraction)
        # -------------------------------------------------------------
        if cls.is_ai_enabled():
            try:
                provider = get_llm_provider()
                system_prompt = (
                    "You are MedPilot's authoritative medical curriculum matching engine.\n"
                    "Your task is to identify which official syllabus unit best matches the student's exam portion query.\n"
                    "RULES:\n"
                    "1. You MUST select strictly from the provided candidate units list, or return null if none match.\n"
                    "2. Do NOT invent new units or topics.\n"
                    "3. Assign a confidence_score between 0.0 and 1.0 based on medical certainty.\n"
                    "Return strictly JSON with keys:\n"
                    "- 'matched_unit': string (exact candidate unit name) or null\n"
                    "- 'confidence_score': float between 0.0 and 1.0\n"
                    "- 'reasoning': concise explanation"
                )
                user_prompt = (
                    f"Subject: {subject_name}\n"
                    f"Candidate Syllabus Units: {json.dumps(available_portions)}\n"
                    f"Student Query: '{q}'\n\n"
                    "Identify the matching syllabus unit from the candidates."
                )

                ai_res = await provider.generate_json(system_prompt, user_prompt)
                ai_unit = ai_res.get("matched_unit")
                ai_score = float(ai_res.get("confidence_score", 0.0) or 0.0)

                # Strictly validate that AI returned an item from available_portions
                if ai_unit and ai_unit in available_portions:
                    if ai_score >= 0.75:
                        return {
                            "matched_portion": ai_unit,
                            "confidence": "high",
                            "confidence_score": ai_score,
                            "match_message": None,
                            "ai_assisted": True
                        }
                    elif ai_score >= 0.45:
                        return {
                            "matched_portion": ai_unit,
                            "confidence": "medium",
                            "confidence_score": ai_score,
                            "match_message": f"Did you mean {ai_unit}?",
                            "ai_assisted": True
                        }
                    else:
                        return {
                            "matched_portion": None,
                            "confidence": "low",
                            "confidence_score": ai_score,
                            "match_message": "We couldn't confidently match this portion to the syllabus. Add topics manually or choose a syllabus unit.",
                            "ai_assisted": True
                        }
            except Exception as e:
                logger.warning(f"AI portion matching failed: {e}. Falling back to deterministic matching.")

        # -------------------------------------------------------------
        # 5. Deterministic Fallback if AI is offline or low confidence
        # -------------------------------------------------------------
        if token_scores:
            best_unit, best_score = token_scores[0]
            if best_score >= 0.45:
                return {
                    "matched_portion": best_unit,
                    "confidence": "medium",
                    "confidence_score": best_score,
                    "match_message": f"Did you mean {best_unit}?",
                    "ai_assisted": False
                }

        # Low confidence fallback
        return {
            "matched_portion": None,
            "confidence": "low",
            "confidence_score": 0.20,
            "match_message": "We couldn't confidently match this portion to the syllabus. Add topics manually or choose a syllabus unit.",
            "ai_assisted": False
        }

    @classmethod
    async def rank_verified_topics_hybrid(
        cls,
        verified_topics: List[str],
        subject_name: str,
        portion_name: Optional[str] = None,
        days_remaining: Optional[int] = None,
        target_score: Optional[float] = None,
        missed_topics: Optional[List[str]] = None,
        flagged_feedback_topics: Optional[List[str]] = None
    ) -> Tuple[List[str], bool]:
        """
        Ranks verified syllabus topics based on academic context.
        SAFETY INVARIANTS:
        - Input MUST be strictly verified topics from MedPilot's curriculum.
        - AI is ONLY used to reorder / rank existing verified items.
        - Any topic returned by AI that is not in verified_topics is discarded.
        - Any verified topic omitted by AI is safely appended to maintain completeness.
        - Subject / unit mappings are never altered.
        """
        if not verified_topics or len(verified_topics) <= 1:
            return verified_topics, False

        missed_set = set(t.lower().strip() for t in (missed_topics or []))
        feedback_set = set(t.lower().strip() for t in (flagged_feedback_topics or []))

        # 1. Check if AI ranking is possible
        if cls.is_ai_enabled():
            try:
                provider = get_llm_provider()
                system_prompt = (
                    "You are MedPilot's medical exam revision ranker.\n"
                    "Your job is to rank a list of VERIFIED syllabus topics in order of highest academic priority and exam yield.\n"
                    "CRITICAL SAFETY RULES:\n"
                    "1. Return ONLY topics from the verified candidate list. Do NOT invent, rename, or add any new topics.\n"
                    "2. Return strictly JSON with key 'ranked_topics': array of strings.\n"
                    "3. Prioritize high-yield topics, urgent exam yield, and areas needing catch-up."
                )
                user_prompt = (
                    f"Subject: {subject_name}\n"
                    f"Exam Portion: {portion_name or 'All Units'}\n"
                    f"Days until exam: {days_remaining if days_remaining is not None else 'Not specified'}\n"
                    f"Target score: {target_score if target_score is not None else 75.0}%\n"
                    f"Topics student missed in class: {list(missed_set)}\n"
                    f"Topics student flagged as hard or needing more time: {list(feedback_set)}\n\n"
                    f"Verified Topics to Rank:\n{json.dumps(verified_topics)}"
                )

                ai_res = await provider.generate_json(system_prompt, user_prompt)
                ranked_raw = ai_res.get("ranked_topics")
                if isinstance(ranked_raw, list) and len(ranked_raw) > 0:
                    # Strict validation against verified_topics
                    valid_map = {t.lower().strip(): t for t in verified_topics}
                    final_ranked = []
                    seen = set()

                    for item in ranked_raw:
                        if isinstance(item, str):
                            k = item.lower().strip()
                            if k in valid_map and k not in seen:
                                final_ranked.append(valid_map[k])
                                seen.add(k)

                    # Append any verified topics that were omitted by the LLM
                    for t in verified_topics:
                        k = t.lower().strip()
                        if k not in seen:
                            final_ranked.append(t)
                            seen.add(k)

                    if len(final_ranked) == len(verified_topics):
                        return final_ranked, True
            except Exception as e:
                logger.warning(f"AI topic ranking failed: {e}. Falling back to deterministic ranking.")

        # 2. Deterministic Academic Context Ranking Fallback
        def topic_sort_key(t: str) -> Tuple[int, int, int]:
            k = t.lower().strip()
            # Priority 0: Missed in class
            is_missed = 0 if k in missed_set or any(m in k for m in missed_set) else 1
            # Priority 1: Flagged as hard or need more time
            is_feedback = 0 if k in feedback_set or any(f in k for f in feedback_set) else 1
            return (is_missed, is_feedback, 0)

        sorted_topics = sorted(verified_topics, key=topic_sort_key)
        return sorted_topics, False
