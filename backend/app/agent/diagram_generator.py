import html
import base64
from typing import Dict, Any, Optional


class MedicalDiagramGenerator:
    """
    Generates original, high-clarity, labeled educational SVG diagrams for medical students.
    Strictly original schematics; does not reproduce copyrighted textbook artwork.
    """

    @classmethod
    def generate_diagram(cls, topic: str, description: Optional[str] = None) -> Dict[str, Any]:
        t_lower = topic.lower()

        if any(w in t_lower for w in ["brachial plexus", "upper limb", "arm nerve", "plexus"]):
            svg_content = cls._generate_brachial_plexus_svg()
            mermaid_code = cls._generate_brachial_plexus_mermaid()
            title = "Brachial Plexus Schematic Diagram (Roots to Terminal Branches)"
            caption = "Original high-yield schematic of the Brachial Plexus (C5-T1) showing Roots, Trunks, Divisions, Cords, Terminal Nerves, and Clinical Lesion Sites (Erb's & Klumpke's)."
        elif any(w in t_lower for w in ["nephron", "renal", "kidney", "glomerulus", "loop of henle"]):
            svg_content = cls._generate_nephron_svg()
            mermaid_code = cls._generate_nephron_mermaid()
            title = "Nephron Functional Schematic & Tubular Transport"
            caption = "Original anatomical diagram of the Nephron illustrating Glomerular Filtration, Proximal Tubule reabsorption, Loop of Henle countercurrent gradient, DCT, and Collecting Duct."
        elif any(w in t_lower for w in ["glycolysis", "embden-meyerhof", "glucose oxidation", "metabolic pathway"]):
            svg_content = cls._generate_glycolysis_svg()
            mermaid_code = cls._generate_glycolysis_mermaid()
            title = "Glycolysis 10-Step Metabolic Schematic Flowchart"
            caption = "Original metabolic diagram highlighting Preparatory (-2 ATP) and Payoff (+4 ATP, +2 NADH) phases with key irreversible regulatory enzymes: Hexokinase, PFK-1, and Pyruvate Kinase."
        else:
            svg_content = cls._generate_generic_medical_svg(topic, description or "")
            mermaid_code = cls._generate_generic_medical_mermaid(topic, description or "")
            title = f"Educational Schematic: {topic.title()}"
            caption = f"MedPilot original schematic representation of {topic} for conceptual revision."

        # Encode SVG as data URL
        b64_svg = base64.b64encode(svg_content.encode("utf-8")).decode("utf-8")
        image_url = f"data:image/svg+xml;base64,{b64_svg}"

        return {
            "title": title,
            "caption": caption,
            "image_url": image_url,
            "diagram_type": "schematic_diagram",
            "svg_content": svg_content,
            "mermaid_code": mermaid_code
        }

    @classmethod
    def _generate_brachial_plexus_mermaid(cls) -> str:
        return """graph TD
    classDef roots fill:#CFEDE7,stroke:#0D9488,stroke-width:2px,color:#042F2E;
    classDef trunks fill:#B7D4F4,stroke:#2563EB,stroke-width:2px,color:#1E3A8A;
    classDef cords fill:#FDE68A,stroke:#CA8A04,stroke-width:2px,color:#713F12;
    classDef branches fill:#FED7AA,stroke:#EA580C,stroke-width:2px,color:#7C2D12;

    C5["Root C5"]:::roots
    C6["Root C6"]:::roots
    C7["Root C7"]:::roots
    C8["Root C8"]:::roots
    T1["Root T1"]:::roots

    UT["Upper Trunk (C5, C6)"]:::trunks
    MT["Middle Trunk (C7)"]:::trunks
    LT["Lower Trunk (C8, T1)"]:::trunks

    C5 --> UT
    C6 --> UT
    C7 --> MT
    C8 --> LT
    T1 --> LT

    LC["Lateral Cord"]:::cords
    PC["Posterior Cord"]:::cords
    MC["Medial Cord"]:::cords

    UT -->|"Ant Div"| LC
    MT -->|"Ant Div"| LC
    UT -->|"Post Div"| PC
    MT -->|"Post Div"| PC
    LT -->|"Post Div"| PC
    LT -->|"Ant Div"| MC

    MC_N["Musculocutaneous Nerve"]:::branches
    AX_N["Axillary Nerve"]:::branches
    RAD_N["Radial Nerve"]:::branches
    MED_N["Median Nerve"]:::branches
    ULN_N["Ulnar Nerve"]:::branches

    LC --> MC_N
    LC -->|"Lat Root"| MED_N
    MC -->|"Med Root"| MED_N
    MC --> ULN_N
    PC --> AX_N
    PC --> RAD_N"""

    @classmethod
    def _generate_nephron_mermaid(cls) -> str:
        return """graph LR
    classDef filter fill:#FEE2E2,stroke:#EF4444,stroke-width:2px,color:#7F1D1D;
    classDef reabsorb fill:#CCFBF1,stroke:#0D9488,stroke-width:2px,color:#0F766E;
    classDef loop fill:#DBEAFE,stroke:#3B82F6,stroke-width:2px,color:#1D4ED8;
    classDef dct fill:#FEF3C7,stroke:#F59E0B,stroke-width:2px,color:#92400E;
    classDef cd fill:#FCE7F3,stroke:#EC4899,stroke-width:2px,color:#9D174D;

    GLOM["Glomerulus & Bowman Capsule<br/>(GFR 125 mL/min)"]:::filter
    PCT["Proximal Convoluted Tubule<br/>(65% Na+, H2O, 100% Glucose)"]:::reabsorb
    DTL["Descending Thin Limb<br/>(H2O Permeable)"]:::loop
    TAL["Thick Ascending Limb<br/>(Active NKCC2 cotransporter)"]:::loop
    DCT["Distal Convoluted Tubule<br/>(Na+/Cl- Cotransport, PTH)"]:::dct
    CD["Collecting Duct<br/>(Aldosterone ENaC | ADH AQP-2)"]:::cd
    URINE["Renal Pelvis (Urine Excretion)"]

    GLOM --> PCT --> DTL --> TAL --> DCT --> CD --> URINE"""

    @classmethod
    def _generate_glycolysis_mermaid(cls) -> str:
        return """graph TD
    classDef reg fill:#FEE2E2,stroke:#EF4444,stroke-width:2px,color:#991B1B;
    classDef payoff fill:#DCFCE7,stroke:#16A34A,stroke-width:2px,color:#166534;

    G["Glucose (6C)"]
    G -->|"1. Hexokinase / GK [-1 ATP]"| G6P["Glucose-6-Phosphate"]:::reg
    G6P -->|"2. Phosphohexose Isomerase"| F6P["Fructose-6-Phosphate"]
    F6P -->|"3. PFK-1 (Rate-Limiting) [-1 ATP]"| F16BP["Fructose-1,6-Bisphosphate"]:::reg
    F16BP -->|"4. Aldolase"| SPLIT["DHAP <--> G3P (x2)"]

    SPLIT -->|"6. G3P Dehydrogenase [+2 NADH]"| BPG["2x 1,3-Bisphosphoglycerate"]:::payoff
    BPG -->|"7. Phosphoglycerate Kinase [+2 ATP]"| PG3["2x 3-Phosphoglycerate"]:::payoff
    PG3 -->|"8. Phosphoglycerate Mutase"| PG2["2x 2-Phosphoglycerate"]
    PG2 -->|"9. Enolase"| PEP["2x Phosphoenolpyruvate"]
    PEP -->|"10. Pyruvate Kinase [+2 ATP]"| PYR["2x Pyruvate (3C)"]:::reg"""

    @classmethod
    def _generate_generic_medical_mermaid(cls, topic: str, description: str) -> str:
        clean_title = topic.replace('"', '').title()
        return f"""graph TD
    T["{clean_title}"]
    T --> A["1. Anatomical & Structural Framework"]
    T --> B["2. Physiological Mechanism & Regulation"]
    T --> C["3. Clinical & Pathology Correlations"]"""


    @classmethod
    def _generate_brachial_plexus_svg(cls) -> str:
        return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 950 560" width="100%" height="100%" style="background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <defs>
    <linearGradient id="rootGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#CFEDE7" />
      <stop offset="100%" stop-color="#A7E4D8" />
    </linearGradient>
    <linearGradient id="trunkGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#B7D4F4" />
      <stop offset="100%" stop-color="#93C5FD" />
    </linearGradient>
    <linearGradient id="cordGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FDE68A" />
      <stop offset="100%" stop-color="#FCD34D" />
    </linearGradient>
    <linearGradient id="branchGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FED7AA" />
      <stop offset="100%" stop-color="#FDBA74" />
    </linearGradient>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="115%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#0F172A" flood-opacity="0.06"/>
    </filter>
  </defs>

  <!-- Title & Subtitle Header -->
  <rect x="25" y="16" width="900" height="52" rx="12" fill="#FFFFFF" stroke="#E2E8F0" filter="url(#shadow)"/>
  <text x="45" y="42" font-size="16" font-weight="700" fill="#0F172A">Brachial Plexus Schematic Diagram (Roots C5-T1 to Terminal Nerves)</text>
  <text x="45" y="58" font-size="11" fill="#64748B">MBBS First-Year Anatomy • High-Yield Relations • Clinical Points (Erb's &amp; Klumpke's)</text>

  <!-- Column Header Badges -->
  <!-- 1. ROOTS -->
  <rect x="40" y="82" width="130" height="30" rx="8" fill="#134E4A" />
  <text x="105" y="102" font-size="12" font-weight="700" fill="#FFFFFF" text-anchor="middle">5 ROOTS (VPR)</text>

  <!-- 2. TRUNKS -->
  <rect x="210" y="82" width="130" height="30" rx="8" fill="#1E3A8A" />
  <text x="275" y="102" font-size="12" font-weight="700" fill="#FFFFFF" text-anchor="middle">3 TRUNKS</text>

  <!-- 3. DIVISIONS -->
  <rect x="380" y="82" width="130" height="30" rx="8" fill="#475569" />
  <text x="445" y="102" font-size="12" font-weight="700" fill="#FFFFFF" text-anchor="middle">6 DIVISIONS (Ant/Post)</text>

  <!-- 4. CORDS -->
  <rect x="550" y="82" width="130" height="30" rx="8" fill="#854D0E" />
  <text x="615" y="102" font-size="12" font-weight="700" fill="#FFFFFF" text-anchor="middle">3 CORDS</text>

  <!-- 5. BRANCHES -->
  <rect x="720" y="82" width="190" height="30" rx="8" fill="#9A3412" />
  <text x="815" y="102" font-size="12" font-weight="700" fill="#FFFFFF" text-anchor="middle">5 TERMINAL BRANCHES</text>

  <!-- Connecting Lines -->
  <!-- Roots C5, C6 -> Upper Trunk -->
  <path d="M 170 145 C 190 145, 190 170, 210 170" stroke="#0D9488" stroke-width="3" fill="none" stroke-linecap="round"/>
  <path d="M 170 215 C 190 215, 190 170, 210 170" stroke="#0D9488" stroke-width="3" fill="none" stroke-linecap="round"/>

  <!-- Root C7 -> Middle Trunk -->
  <path d="M 170 285 L 210 285" stroke="#0D9488" stroke-width="3" fill="none" stroke-linecap="round"/>

  <!-- Roots C8, T1 -> Lower Trunk -->
  <path d="M 170 355 C 190 355, 190 400, 210 400" stroke="#0D9488" stroke-width="3" fill="none" stroke-linecap="round"/>
  <path d="M 170 445 C 190 445, 190 400, 210 400" stroke="#0D9488" stroke-width="3" fill="none" stroke-linecap="round"/>

  <!-- Trunks -> Divisions -> Cords -->
  <!-- Upper Trunk to Lateral Cord (via Ant Div) -->
  <path d="M 340 170 L 380 170 L 510 170 L 550 200" stroke="#2563EB" stroke-width="3" fill="none"/>
  <!-- Middle Trunk to Lateral Cord (via Ant Div) -->
  <path d="M 340 285 C 410 285, 460 200, 550 200" stroke="#2563EB" stroke-width="2.5" fill="none"/>

  <!-- Posterior Divisions of all 3 trunks -> Posterior Cord -->
  <path d="M 340 170 C 400 170, 470 300, 550 300" stroke="#64748B" stroke-dasharray="4,4" stroke-width="2.5" fill="none"/>
  <path d="M 340 285 L 550 300" stroke="#64748B" stroke-dasharray="4,4" stroke-width="2.5" fill="none"/>
  <path d="M 340 400 C 400 400, 470 300, 550 300" stroke="#64748B" stroke-dasharray="4,4" stroke-width="2.5" fill="none"/>

  <!-- Lower Trunk to Medial Cord (via Ant Div) -->
  <path d="M 340 400 L 550 400" stroke="#2563EB" stroke-width="3" fill="none"/>

  <!-- Cords -> Terminal Branches -->
  <!-- Lateral Cord -> Musculocutaneous & Lateral Root of Median -->
  <path d="M 680 200 L 720 150" stroke="#D97706" stroke-width="3" fill="none"/>
  <path d="M 680 200 C 700 200, 710 330, 720 330" stroke="#D97706" stroke-width="2.5" fill="none"/>

  <!-- Posterior Cord -> Axillary & Radial -->
  <path d="M 680 300 L 720 220" stroke="#D97706" stroke-width="2.5" fill="none"/>
  <path d="M 680 300 L 720 275" stroke="#D97706" stroke-width="3" fill="none"/>

  <!-- Medial Cord -> Medial Root of Median & Ulnar -->
  <path d="M 680 400 C 700 400, 710 330, 720 330" stroke="#D97706" stroke-width="2.5" fill="none"/>
  <path d="M 680 400 L 720 400" stroke="#D97706" stroke-width="3" fill="none"/>

  <!-- NODES: ROOTS -->
  <g filter="url(#shadow)">
    <rect x="40" y="125" width="130" height="40" rx="8" fill="url(#rootGrad)" stroke="#0D9488" stroke-width="1.5"/>
    <text x="105" y="150" font-size="13" font-weight="700" fill="#042F2E" text-anchor="middle">Root C5</text>

    <rect x="40" y="195" width="130" height="40" rx="8" fill="url(#rootGrad)" stroke="#0D9488" stroke-width="1.5"/>
    <text x="105" y="220" font-size="13" font-weight="700" fill="#042F2E" text-anchor="middle">Root C6</text>

    <rect x="40" y="265" width="130" height="40" rx="8" fill="url(#rootGrad)" stroke="#0D9488" stroke-width="1.5"/>
    <text x="105" y="290" font-size="13" font-weight="700" fill="#042F2E" text-anchor="middle">Root C7</text>

    <rect x="40" y="335" width="130" height="40" rx="8" fill="url(#rootGrad)" stroke="#0D9488" stroke-width="1.5"/>
    <text x="105" y="360" font-size="13" font-weight="700" fill="#042F2E" text-anchor="middle">Root C8</text>

    <rect x="40" y="425" width="130" height="40" rx="8" fill="url(#rootGrad)" stroke="#0D9488" stroke-width="1.5"/>
    <text x="105" y="450" font-size="13" font-weight="700" fill="#042F2E" text-anchor="middle">Root T1</text>
  </g>

  <!-- NODES: TRUNKS -->
  <g filter="url(#shadow)">
    <rect x="210" y="145" width="130" height="50" rx="8" fill="url(#trunkGrad)" stroke="#2563EB" stroke-width="1.5"/>
    <text x="275" y="170" font-size="12" font-weight="700" fill="#1E3A8A" text-anchor="middle">UPPER TRUNK</text>
    <text x="275" y="185" font-size="10" fill="#1E40AF" text-anchor="middle">(C5, C6)</text>

    <rect x="210" y="260" width="130" height="50" rx="8" fill="url(#trunkGrad)" stroke="#2563EB" stroke-width="1.5"/>
    <text x="275" y="285" font-size="12" font-weight="700" fill="#1E3A8A" text-anchor="middle">MIDDLE TRUNK</text>
    <text x="275" y="300" font-size="10" fill="#1E40AF" text-anchor="middle">(C7)</text>

    <rect x="210" y="375" width="130" height="50" rx="8" fill="url(#trunkGrad)" stroke="#2563EB" stroke-width="1.5"/>
    <text x="275" y="400" font-size="12" font-weight="700" fill="#1E3A8A" text-anchor="middle">LOWER TRUNK</text>
    <text x="275" y="415" font-size="10" fill="#1E40AF" text-anchor="middle">(C8, T1)</text>
  </g>

  <!-- NODES: CORDS -->
  <g filter="url(#shadow)">
    <rect x="550" y="175" width="130" height="50" rx="8" fill="url(#cordGrad)" stroke="#CA8A04" stroke-width="1.5"/>
    <text x="615" y="200" font-size="12" font-weight="700" fill="#713F12" text-anchor="middle">LATERAL CORD</text>
    <text x="615" y="215" font-size="10" fill="#854D0E" text-anchor="middle">(C5, C6, C7)</text>

    <rect x="550" y="275" width="130" height="50" rx="8" fill="url(#cordGrad)" stroke="#CA8A04" stroke-width="1.5"/>
    <text x="615" y="300" font-size="12" font-weight="700" fill="#713F12" text-anchor="middle">POSTERIOR CORD</text>
    <text x="615" y="315" font-size="10" fill="#854D0E" text-anchor="middle">(C5 - T1 all)</text>

    <rect x="550" y="375" width="130" height="50" rx="8" fill="url(#cordGrad)" stroke="#CA8A04" stroke-width="1.5"/>
    <text x="615" y="400" font-size="12" font-weight="700" fill="#713F12" text-anchor="middle">MEDIAL CORD</text>
    <text x="615" y="415" font-size="10" fill="#854D0E" text-anchor="middle">(C8, T1)</text>
  </g>

  <!-- NODES: TERMINAL BRANCHES -->
  <g filter="url(#shadow)">
    <rect x="720" y="130" width="190" height="40" rx="8" fill="url(#branchGrad)" stroke="#EA580C" stroke-width="1.5"/>
    <text x="815" y="155" font-size="12" font-weight="700" fill="#7C2D12" text-anchor="middle">Musculocutaneous Nerve</text>

    <rect x="720" y="200" width="190" height="40" rx="8" fill="url(#branchGrad)" stroke="#EA580C" stroke-width="1.5"/>
    <text x="815" y="225" font-size="12" font-weight="700" fill="#7C2D12" text-anchor="middle">Axillary Nerve (C5, C6)</text>

    <rect x="720" y="255" width="190" height="40" rx="8" fill="url(#branchGrad)" stroke="#EA580C" stroke-width="1.5"/>
    <text x="815" y="280" font-size="12" font-weight="700" fill="#7C2D12" text-anchor="middle">Radial Nerve (C5-T1)</text>

    <rect x="720" y="310" width="190" height="40" rx="8" fill="url(#branchGrad)" stroke="#EA580C" stroke-width="1.5"/>
    <text x="815" y="335" font-size="12" font-weight="700" fill="#7C2D12" text-anchor="middle">Median Nerve (C5-T1)</text>

    <rect x="720" y="380" width="190" height="40" rx="8" fill="url(#branchGrad)" stroke="#EA580C" stroke-width="1.5"/>
    <text x="815" y="405" font-size="12" font-weight="700" fill="#7C2D12" text-anchor="middle">Ulnar Nerve (C8, T1)</text>
  </g>

  <!-- Clinical Markers -->
  <!-- Erb's Point Marker -->
  <circle cx="210" cy="155" r="8" fill="#EF4444" stroke="#FFFFFF" stroke-width="2"/>
  <rect x="180" y="115" width="95" height="22" rx="4" fill="#FEE2E2" stroke="#EF4444" stroke-width="1"/>
  <text x="227" y="130" font-size="10" font-weight="700" fill="#991B1B" text-anchor="middle">Erb's Point (C5-6)</text>

  <!-- Klumpke Marker -->
  <circle cx="210" cy="415" r="8" fill="#EF4444" stroke="#FFFFFF" stroke-width="2"/>
  <rect x="175" y="430" width="115" height="22" rx="4" fill="#FEE2E2" stroke="#EF4444" stroke-width="1"/>
  <text x="232" y="445" font-size="10" font-weight="700" fill="#991B1B" text-anchor="middle">Klumpke Point (C8-T1)</text>

  <!-- Footer Banner: Clinical Pearl -->
  <rect x="40" y="490" width="870" height="45" rx="8" fill="#F1F5F9" stroke="#CBD5E1"/>
  <text x="55" y="512" font-size="11" font-weight="700" fill="#0F172A">Clinical Pearls:</text>
  <text x="145" y="512" font-size="11" fill="#334155">• Erb-Duchenne Palsy (Upper trunk): "Waiter's tip / Policeman's tip" deformity (loss of abductors &amp; lateral rotators).</text>
  <text x="145" y="527" font-size="11" fill="#334155">• Klumpke Palsy (Lower trunk): Claw hand deformity (intrinsic hand paralysis) ± Horner's syndrome (T1 sympathetic chain).</text>
</svg>"""

    @classmethod
    def _generate_nephron_svg(cls) -> str:
        return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 950 560" width="100%" height="100%" style="background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <defs>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="115%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#0F172A" flood-opacity="0.06"/>
    </filter>
  </defs>

  <!-- Header -->
  <rect x="25" y="16" width="900" height="52" rx="12" fill="#FFFFFF" stroke="#E2E8F0" filter="url(#shadow)"/>
  <text x="45" y="42" font-size="16" font-weight="700" fill="#0F172A">Nephron Functional Schematic &amp; Tubular Transport</text>
  <text x="45" y="58" font-size="11" fill="#64748B">Renal Physiology • Glomerular Filtration • Countercurrent Multiplier • Hormonal Control</text>

  <!-- Renal Cortex vs Medulla Background Line -->
  <line x1="40" y1="210" x2="910" y2="210" stroke="#CBD5E1" stroke-dasharray="6,6" stroke-width="2"/>
  <rect x="800" y="185" width="100" height="22" rx="4" fill="#F1F5F9" stroke="#94A3B8"/>
  <text x="850" y="200" font-size="10" font-weight="700" fill="#475569" text-anchor="middle">CORTEX</text>
  <rect x="800" y="215" width="100" height="22" rx="4" fill="#FEF2F2" stroke="#F87171"/>
  <text x="850" y="230" font-size="10" font-weight="700" fill="#991B1B" text-anchor="middle">MEDULLA</text>

  <!-- 1. GLOMERULUS & BOWMAN'S CAPSULE -->
  <g filter="url(#shadow)">
    <circle cx="120" cy="140" r="45" fill="#FEE2E2" stroke="#EF4444" stroke-width="3"/>
    <circle cx="120" cy="140" r="28" fill="#FCA5A5" stroke="#B91C1C" stroke-width="2"/>
    <text x="120" y="136" font-size="11" font-weight="700" fill="#7F1D1D" text-anchor="middle">Glomerulus</text>
    <text x="120" y="150" font-size="9" fill="#991B1B" text-anchor="middle">(GFR 125 mL/min)</text>

    <!-- Afferent & Efferent Arterioles -->
    <path d="M 40 120 L 92 125" stroke="#DC2626" stroke-width="6" stroke-linecap="round"/>
    <text x="50" y="112" font-size="9" font-weight="700" fill="#991B1B">Afferent</text>

    <path d="M 92 155 L 40 160" stroke="#DC2626" stroke-width="4" stroke-linecap="round"/>
    <text x="50" y="175" font-size="9" font-weight="700" fill="#991B1B">Efferent</text>
  </g>

  <!-- 2. PROXIMAL CONVOLUTED TUBULE (PCT) -->
  <g filter="url(#shadow)">
    <path d="M 165 140 C 200 90, 240 190, 280 140 C 310 100, 330 180, 360 140" stroke="#0D9488" stroke-width="12" fill="none" stroke-linecap="round"/>
    <rect x="210" y="80" width="135" height="42" rx="6" fill="#CCFBF1" stroke="#14B8A6"/>
    <text x="277" y="97" font-size="11" font-weight="700" fill="#0F766E" text-anchor="middle">PCT Reabsorption</text>
    <text x="277" y="112" font-size="9" fill="#115E59" text-anchor="middle">65% Na+, H2O, 100% Glucose</text>
  </g>

  <!-- 3. LOOP OF HENLE -->
  <!-- Descending Limb (Thin) -->
  <path d="M 360 140 L 360 410" stroke="#3B82F6" stroke-width="8" fill="none"/>
  <!-- Hairpin Turn -->
  <path d="M 360 410 C 360 450, 440 450, 440 410" stroke="#6366F1" stroke-width="10" fill="none"/>
  <!-- Ascending Limb (Thick TAL) -->
  <path d="M 440 410 L 440 140" stroke="#8B5CF6" stroke-width="14" fill="none"/>

  <!-- Transport Labels for Loop of Henle -->
  <rect x="250" y="270" width="105" height="38" rx="6" fill="#DBEAFE" stroke="#60A5FA"/>
  <text x="302" y="286" font-size="10" font-weight="700" fill="#1D4ED8" text-anchor="middle">Descending Limb</text>
  <text x="302" y="300" font-size="8.5" fill="#1E40AF" text-anchor="middle">Permeable to H2O only</text>

  <rect x="450" y="270" width="135" height="45" rx="6" fill="#EDE9FE" stroke="#A78BFA"/>
  <text x="517" y="287" font-size="10" font-weight="700" fill="#5B21B6" text-anchor="middle">Thick Ascending (TAL)</text>
  <text x="517" y="301" font-size="8.5" fill="#6D28D9" text-anchor="middle">Active NKCC2 cotransporter</text>
  <text x="517" y="312" font-size="8" fill="#7C3AED" text-anchor="middle">(Loop Diuretics target)</text>

  <!-- 4. DISTAL CONVOLUTED TUBULE (DCT) -->
  <path d="M 440 140 C 470 100, 520 180, 560 140 C 590 110, 620 160, 650 140" stroke="#F59E0B" stroke-width="12" fill="none" stroke-linecap="round"/>
  <rect x="495" y="80" width="130" height="42" rx="6" fill="#FEF3C7" stroke="#FBBF24"/>
  <text x="560" y="97" font-size="11" font-weight="700" fill="#92400E" text-anchor="middle">DCT Tuning</text>
  <text x="560" y="112" font-size="9" fill="#B45309" text-anchor="middle">Na+/Cl- (Thiazides), PTH</text>

  <!-- 5. COLLECTING DUCT -->
  <path d="M 650 140 L 720 140 L 720 470" stroke="#EC4899" stroke-width="16" fill="none"/>
  <rect x="740" y="220" width="155" height="52" rx="6" fill="#FCE7F3" stroke="#F472B6"/>
  <text x="817" y="238" font-size="11" font-weight="700" fill="#9D174D" text-anchor="middle">Collecting Duct</text>
  <text x="817" y="253" font-size="9" fill="#BE185D" text-anchor="middle">Principal Cells: Aldosterone (ENaC)</text>
  <text x="817" y="265" font-size="9" fill="#BE185D" text-anchor="middle">ADH: Aquaporin-2 water pores</text>

  <!-- Output Arrow: Urine Excretion -->
  <path d="M 720 470 L 720 515" stroke="#94A3B8" stroke-width="4" marker-end="url(#arrow)"/>
  <rect x="660" y="515" width="120" height="25" rx="5" fill="#E2E8F0"/>
  <text x="720" y="532" font-size="10" font-weight="700" fill="#1E293B" text-anchor="middle">To Renal Pelvis (Urine)</text>

  <!-- Bottom Legend Bar -->
  <rect x="40" y="490" width="580" height="45" rx="8" fill="#FFFFFF" stroke="#E2E8F0"/>
  <text x="55" y="510" font-size="10" font-weight="700" fill="#0F172A">Clinical Pharmacological Correlation:</text>
  <text x="55" y="525" font-size="9.5" fill="#475569">• Acetazolamide: PCT CA enzyme • Furosemide: TAL NKCC2 • Thiazides: DCT NCC • Spironolactone: Collecting Duct MR</text>
</svg>"""

    @classmethod
    def _generate_glycolysis_svg(cls) -> str:
        return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 950 560" width="100%" height="100%" style="background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <defs>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="115%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#0F172A" flood-opacity="0.06"/>
    </filter>
  </defs>

  <!-- Header -->
  <rect x="25" y="16" width="900" height="52" rx="12" fill="#FFFFFF" stroke="#E2E8F0" filter="url(#shadow)"/>
  <text x="45" y="42" font-size="16" font-weight="700" fill="#0F172A">Glycolysis 10-Step Metabolic Flowchart (Cytoplasm)</text>
  <text x="45" y="58" font-size="11" fill="#64748B">MBBS First-Year Biochemistry • Energy Investment vs Payoff • 3 Irreversible Regulatory Enzymes</text>

  <!-- Phase 1: Preparatory Phase Box -->
  <rect x="35" y="80" width="420" height="400" rx="10" fill="#FFF7ED" stroke="#FDBA74" stroke-dasharray="4,4"/>
  <rect x="45" y="90" width="230" height="24" rx="6" fill="#FFEDD5"/>
  <text x="160" y="106" font-size="11" font-weight="700" fill="#9A3412" text-anchor="middle">PHASE 1: INVESTMENT (-2 ATP)</text>

  <!-- Step 1 -->
  <rect x="55" y="125" width="200" height="34" rx="6" fill="#FFFFFF" stroke="#CBD5E1" filter="url(#shadow)"/>
  <text x="155" y="146" font-size="11" font-weight="600" fill="#1E293B" text-anchor="middle">Glucose (6C)</text>
  <!-- Enzyme 1 (Irreversible) -->
  <rect x="270" y="130" width="170" height="40" rx="6" fill="#FEE2E2" stroke="#EF4444"/>
  <text x="355" y="147" font-size="10" font-weight="700" fill="#991B1B" text-anchor="middle">1. Hexokinase / GK [★]</text>
  <text x="355" y="160" font-size="8.5" fill="#B91C1C" text-anchor="middle">-1 ATP (Irreversible)</text>

  <!-- Step 2 -->
  <rect x="55" y="180" width="200" height="34" rx="6" fill="#FFFFFF" stroke="#CBD5E1" filter="url(#shadow)"/>
  <text x="155" y="201" font-size="11" font-weight="600" fill="#1E293B" text-anchor="middle">Glucose-6-Phosphate</text>

  <!-- Step 3 (COMMITTED STEP) -->
  <rect x="55" y="240" width="200" height="34" rx="6" fill="#FFFFFF" stroke="#CBD5E1" filter="url(#shadow)"/>
  <text x="155" y="261" font-size="11" font-weight="600" fill="#1E293B" text-anchor="middle">Fructose-6-Phosphate</text>
  <!-- Enzyme 3 (Rate-limiting) -->
  <rect x="270" y="240" width="170" height="50" rx="6" fill="#FEF2F2" stroke="#DC2626" stroke-width="2"/>
  <text x="355" y="258" font-size="10" font-weight="700" fill="#7F1D1D" text-anchor="middle">3. PFK-1 (Rate-Limiting) [★]</text>
  <text x="355" y="271" font-size="8.5" fill="#991B1B" text-anchor="middle">-1 ATP • Inhibited by ATP/Citrate</text>
  <text x="355" y="283" font-size="8.5" fill="#15803D" text-anchor="middle">Stimulated by F-2,6-BP / AMP</text>

  <!-- Step 4 & 5 -->
  <rect x="55" y="315" width="200" height="34" rx="6" fill="#FFFFFF" stroke="#CBD5E1" filter="url(#shadow)"/>
  <text x="155" y="336" font-size="11" font-weight="600" fill="#1E293B" text-anchor="middle">Fructose-1,6-Bisphosphate</text>

  <rect x="55" y="380" width="200" height="42" rx="6" fill="#EFF6FF" stroke="#93C5FD"/>
  <text x="155" y="398" font-size="10" font-weight="700" fill="#1E40AF" text-anchor="middle">Cleavage (Aldolase):</text>
  <text x="155" y="412" font-size="9" fill="#2563EB" text-anchor="middle">DHAP ⟷ Glyceraldehyde-3-P (x2)</text>

  <!-- Phase 2: Payoff Phase Box -->
  <rect x="490" y="80" width="425" height="400" rx="10" fill="#F0FDF4" stroke="#86EFAC" stroke-dasharray="4,4"/>
  <rect x="500" y="90" width="260" height="24" rx="6" fill="#DCFCE7"/>
  <text x="630" y="106" font-size="11" font-weight="700" fill="#166534" text-anchor="middle">PHASE 2: PAYOFF (+4 ATP, +2 NADH)</text>

  <!-- Step 6 -->
  <rect x="510" y="130" width="210" height="38" rx="6" fill="#FFFFFF" stroke="#CBD5E1" filter="url(#shadow)"/>
  <text x="615" y="148" font-size="10" font-weight="600" fill="#1E293B" text-anchor="middle">2x 1,3-Bisphosphoglycerate</text>
  <text x="615" y="161" font-size="8.5" fill="#16A34A" text-anchor="middle">G3P Dehydrogenase (+2 NADH)</text>

  <!-- Step 7 -->
  <rect x="510" y="195" width="210" height="38" rx="6" fill="#FFFFFF" stroke="#CBD5E1" filter="url(#shadow)"/>
  <text x="615" y="213" font-size="10" font-weight="600" fill="#1E293B" text-anchor="middle">2x 3-Phosphoglycerate</text>
  <text x="615" y="226" font-size="8.5" fill="#15803D" text-anchor="middle">PGK (+2 ATP by SLP)</text>

  <!-- Step 8 & 9 -->
  <rect x="510" y="260" width="210" height="38" rx="6" fill="#FFFFFF" stroke="#CBD5E1" filter="url(#shadow)"/>
  <text x="615" y="278" font-size="10" font-weight="600" fill="#1E293B" text-anchor="middle">2x Phosphoenolpyruvate (PEP)</text>
  <text x="615" y="291" font-size="8.5" fill="#64748B" text-anchor="middle">Enolase (Fluoride inhibited)</text>

  <!-- Step 10 (PYRUVATE KINASE) -->
  <rect x="510" y="325" width="210" height="42" rx="6" fill="#FEF2F2" stroke="#EF4444" stroke-width="2"/>
  <text x="615" y="344" font-size="10" font-weight="700" fill="#991B1B" text-anchor="middle">10. Pyruvate Kinase [★]</text>
  <text x="615" y="358" font-size="9" fill="#B91C1C" text-anchor="middle">+2 ATP by SLP (Irreversible)</text>

  <!-- Final Product -->
  <rect x="510" y="395" width="210" height="45" rx="8" fill="#14532D"/>
  <text x="615" y="416" font-size="12" font-weight="700" fill="#FFFFFF" text-anchor="middle">2x PYRUVATE (3C)</text>
  <text x="615" y="430" font-size="9.5" fill="#86EFAC" text-anchor="middle">Aerobic: TCA Cycle • Anaerobic: Lactate</text>

  <!-- Net Summary Footer -->
  <rect x="35" y="495" width="880" height="45" rx="8" fill="#F8FAFC" stroke="#E2E8F0"/>
  <text x="55" y="515" font-size="11" font-weight="700" fill="#0F172A">Net Energy Stoichiometry:</text>
  <text x="215" y="515" font-size="11" fill="#334155">Aerobic: Net 2 ATP + 2 NADH (yielding 7 ATP total)</text>
  <text x="55" y="530" font-size="10.5" fill="#64748B">★ 3 Key Irreversible Regulatory Enzymes: 1. Hexokinase/Glucokinase, 3. PFK-1 (committed rate-limiting step), 10. Pyruvate Kinase</text>
</svg>"""

    @classmethod
    def _generate_generic_medical_svg(cls, topic: str, description: str) -> str:
        safe_topic = html.escape(topic)
        safe_desc = html.escape(description[:120]) if description else "MBBS Curriculum High-Yield Conceptual Overview"
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 950 560" width="100%" height="100%" style="background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <rect x="25" y="16" width="900" height="52" rx="12" fill="#FFFFFF" stroke="#E2E8F0"/>
  <text x="45" y="42" font-size="16" font-weight="700" fill="#0F172A">Medical Schematic: {safe_topic}</text>
  <text x="45" y="58" font-size="11" fill="#64748B">{safe_desc}</text>

  <!-- Central Concept Card -->
  <rect x="275" y="100" width="400" height="100" rx="12" fill="#CFEDE7" stroke="#0D9488" stroke-width="2"/>
  <text x="475" y="145" font-size="16" font-weight="700" fill="#042F2E" text-anchor="middle">{safe_topic}</text>
  <text x="475" y="168" font-size="11" fill="#134E4A" text-anchor="middle">Core Anatomical / Physiological Foundation</text>

  <!-- 3 Pillar Columns -->
  <rect x="75" y="240" width="240" height="200" rx="10" fill="#FFFFFF" stroke="#E2E8F0"/>
  <rect x="75" y="240" width="240" height="36" rx="10" fill="#1E3A8A"/>
  <text x="195" y="263" font-size="12" font-weight="700" fill="#FFFFFF" text-anchor="middle">1. Etiology &amp; Anatomy</text>
  <text x="95" y="300" font-size="11" fill="#334155">• Structural boundaries</text>
  <text x="95" y="325" font-size="11" fill="#334155">• Neurovascular supply</text>
  <text x="95" y="350" font-size="11" fill="#334155">• Embryological origin</text>
  <text x="95" y="375" font-size="11" fill="#334155">• Histological hallmarks</text>

  <rect x="355" y="240" width="240" height="200" rx="10" fill="#FFFFFF" stroke="#E2E8F0"/>
  <rect x="355" y="240" width="240" height="36" rx="10" fill="#0F766E"/>
  <text x="475" y="263" font-size="12" font-weight="700" fill="#FFFFFF" text-anchor="middle">2. Mechanism &amp; Pathway</text>
  <text x="375" y="300" font-size="11" fill="#334155">• Biochemical cascade</text>
  <text x="375" y="325" font-size="11" fill="#334155">• Receptors &amp; second messengers</text>
  <text x="375" y="350" font-size="11" fill="#334155">• Rate-limiting enzymes</text>
  <text x="375" y="375" font-size="11" fill="#334155">• Homeostatic regulation</text>

  <rect x="635" y="240" width="240" height="200" rx="10" fill="#FFFFFF" stroke="#E2E8F0"/>
  <rect x="635" y="240" width="240" height="36" rx="10" fill="#9A3412"/>
  <text x="755" y="263" font-size="12" font-weight="700" fill="#FFFFFF" text-anchor="middle">3. Clinical Correlations</text>
  <text x="655" y="300" font-size="11" fill="#334155">• Hallmark clinical signs</text>
  <text x="655" y="325" font-size="11" fill="#334155">• Diagnostic investigations</text>
  <text x="655" y="350" font-size="11" fill="#334155">• Common viva questions</text>
  <text x="655" y="375" font-size="11" fill="#334155">• First-line management</text>

  <!-- Connectors -->
  <path d="M 475 200 L 195 240" stroke="#0D9488" stroke-width="2" stroke-dasharray="4,4"/>
  <path d="M 475 200 L 475 240" stroke="#0D9488" stroke-width="2"/>
  <path d="M 475 200 L 755 240" stroke="#0D9488" stroke-width="2" stroke-dasharray="4,4"/>

  <!-- Footer -->
  <rect x="40" y="475" width="870" height="40" rx="8" fill="#F1F5F9"/>
  <text x="475" y="500" font-size="11" font-weight="600" fill="#475569" text-anchor="middle">MedPilot AI Academic Schematic • Curriculum-Aligned Conceptual Mapping</text>
</svg>"""
