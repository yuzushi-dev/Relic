# Gumi Sweet-Spot Calibration

The sweet-spot report compares the normalized subject vector and candidate Gumi vector.

Required vector dimensions:

- openness
- conscientiousness
- extraversion
- agreeableness
- emotional_stability
- attachment_anxiety
- attachment_avoidance
- directness
- warmth
- initiative
- critique
- playfulness
- diegetic_density
- media_frequency
- autonomy
- boundary_strength

Target similarity is neither clone nor arbitrary opposite. PR28 target range is 0.45 to 0.75, with hard test bounds of 0.35 to 0.80.

Risk components:

- clone_risk
- dependency_risk
- alienation_risk
- overwhelm_risk

The report must store algorithm_version, input vectors, output vectors, scores, recommended adjustments, and researcher review status.
