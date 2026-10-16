# NeuroScope 3D — Quantitative Evaluation (`evaluation/`)

**Area Owner:** Feature Branch `feature/evaluation`  
**Evaluation Target:** Held-out labelled test cases (BraTS 2021) & uploaded expert masks  
**Mandatory Disclaimer:** *Research and teaching prototype only. Not for clinical diagnosis.*

---

## 1. Overview & Formulas

The evaluation module computes quantitative agreement between predicted tumour regions and ground-truth expert masks.

### Metrics Computed:
- **Dice Similarity Coefficient (DSC):**
  $$\text{Dice} = \frac{2 \times |P \cap GT|}{|P| + |GT|}$$
- **Sensitivity (True Positive Rate):**
  $$\text{Sensitivity} = \frac{|P \cap GT|}{|GT|}$$

### Derived Evaluation Regions:
- **WT (Whole Tumour):** Labels `{1, 2, 4}`
- **TC (Tumour Core):** Labels `{1, 4}`
- **ET (Enhancing Tumour):** Label `{4}`

### Empty Mask Edge-Case Rules:
- If $|GT| = 0$ and $|P| = 0$: Dice = 1.0, Sensitivity = 1.0 (true negative agreement).
- If $|GT| = 0$ and $|P| > 0$: Dice = 0.0, Sensitivity = 1.0 (undefined TPR, penalized in Dice).
- If $|GT| > 0$ and $|P| = 0$: Dice = 0.0, Sensitivity = 0.0.

---

## 2. Requirements & Constraints
1. Evaluation must report metrics on at least 10 held-out labelled cases split by patient/case (never by slice).
2. Report aggregate metrics with mean and standard deviation.
3. Disclose known or potential overlap between model training datasets (e.g. BraTS 2018) and evaluation splits.
4. When no expert mask is uploaded for an inference case, do not invent or fabricate case-specific Dice or sensitivity.
