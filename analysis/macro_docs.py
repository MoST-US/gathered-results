"""One-line descriptions of the LaTeX macros written by latex_export.py.

Every macro must be documented here: latex_export.py refuses to write macros.tex if a macro has no
description, so the meaning of each number quoted in the paper stays next to its value.
"""
import re

MODEL = {"DeepSeek": "DeepSeek-R1-Distill-Qwen-7B", "Gemma": "Gemma-7B", "Llama": "Llama-3.1-8B-Instruct"}
TEST = {"MIT": "MIT (2-minute instantaneous test)", "MST": "MST (30-minute sustainable test)"}

STATIC = {
    # data scope
    "NEvaluations": "number of MoST pass/fail SLA evaluations analysed (all runs, after removing exact copies)",
    "NMixRuns": "number of mix runs (MoST searches on request mixes)",
    "NDesigns": "number of distinct mix designs (model x test x composition); unit of the frequentist tests",
    "NRepeatRuns": "number of mix runs that belong to designs measured more than once",
    "NRepeatDesigns": "number of mix designs measured more than once (stability check)",
    "NDuplicates": "number of byte-identical copies of a run found in the archive and counted once",
    "NPureRuns": "number of pure-class runs (one request class per MoST search)",
    # combination law
    "QHatFreq": "power-mean exponent q of the combination law, profile-likelihood estimate (q=-1 harmonic, 0 geometric, +1 arithmetic)",
    "QFreqLo": "lower bound of the 95 % profile-likelihood confidence interval of q",
    "QFreqHi": "upper bound of the 95 % profile-likelihood confidence interval of q",
    "QHatBayes": "power-mean exponent q, Bayesian posterior median (free-q model)",
    "QBayesLo": "lower bound of the 95 % credible interval of q",
    "QBayesHi": "upper bound of the 95 % credible interval of q",
    "HarmonicWinShare": "share of mix runs for which the harmonic prediction is closer to the measurement than the arithmetic one",
    "CalibSlope": "slope of the regression log(measured mix capacity) ~ log(harmonic prediction); 1 = correct scaling",
    "CalibSlopeLo": "lower bound of the 95 % confidence interval of the calibration slope (cluster-robust by model)",
    "CalibSlopeHi": "upper bound of the 95 % confidence interval of the calibration slope",
    "CalibRsq": "R^2 of the calibration regression on the log scale",
    "ArithMeanErr": "mean error of the arithmetic-mean law (measured vs predicted mix capacity, design level); negative = overestimates",
    "GeomMeanErr": "mean error of the geometric-mean law (design level); negative = overestimates",
    "PredFree": "out-of-sample log predictive density of the free-q law minus that of the harmonic law (higher = better)",
    "PredFreeSE": "standard error of PredFree",
    "PredGeom": "out-of-sample log predictive density of the geometric law minus that of the harmonic law",
    "PredGeomSE": "standard error of PredGeom",
    "PredArith": "out-of-sample log predictive density of the arithmetic law minus that of the harmonic law",
    "PredArithSE": "standard error of PredArith",
    # bias and bounds
    "BiasFreq": "mean departure of measured mix capacity from the harmonic prediction, frequentist, designs as units",
    "BiasFreqLo": "lower bound of the 95 % confidence interval of BiasFreq",
    "BiasFreqHi": "upper bound of the 95 % confidence interval of BiasFreq",
    "BiasTostP": "p-value of the TOST equivalence test of the bias against +-10 % (small = practically zero)",
    "BiasBayes": "pooled bias delta_0 of mixes w.r.t. the harmonic law, Bayesian posterior median",
    "BiasBayesLo": "lower bound of the 90 % credible interval of delta_0",
    "BiasBayesHi": "upper bound of the 90 % credible interval of delta_0",
    "BiasBayesPRope": "posterior probability that |delta_0| < 10 % (region of practical equivalence)",
    "BoundsIn": "number of mix runs whose capacity lies between their slowest and fastest class",
    "BoundsN": "number of mix runs checked for boundedness",
    "BoundsShare": "share of mix runs within the capacity range of their classes",
    "AboveArith": "number of mix runs whose capacity exceeds the arithmetic mean of their classes",
    # MIT vs MST, model and heavy class (design level)
    "MitMstMeanP": "p-value (Mann-Whitney) for a difference in mean bias between MIT and MST designs",
    "MitMstLeveneP": "p-value (Levene) for a difference in spread of the errors between MIT and MST",
    "MitMstAbsP": "p-value (Mann-Whitney) for a difference in absolute error between MIT and MST",
    "MitMstLeveneLightP": "Levene p-value for MIT vs MST spread, mixes without the heaviest class only",
    "ModelEffectP": "ANOVA p-value of the model effect on the departure from additivity (controlling test and heavy class)",
    "ModelEffectF": "ANOVA F statistic of the model effect on the departure from additivity",
    "KindEffectP": "ANOVA p-value of the test (MIT/MST) effect on the departure from additivity",
    "ModelEffectLightP": "ANOVA p-value of the model effect, mixes without the heaviest class only",
    "FamilyKwP": "Kruskal-Wallis p-value for differences between mix-design families (equal shares, by cost, 4-5 classes)",
    # Bayesian settings
    "BayesDraws": "NUTS draws per chain (4 chains, same number of tuning steps)",
    "MaxRhat": "largest split-R-hat over the global parameters of the reported Bayesian models (<1.05 = converged)",
    # burst factor
    "BurstMedian": "median burst factor B = MIT/MST over all request classes and models (frequentist)",
    "BurstQOne": "first quartile of the burst factor over all classes",
    "BurstQThree": "third quartile of the burst factor over all classes",
    "BurstOnBand": "share of request classes whose B is within +-15 % of their model's median",
    "BurstNCells": "number of request classes (cells) for which B was measured (3 models x 20 classes)",
    "BurstModelP": "ANOVA p-value of the model effect on log B (controlling input and output range)",
    "BurstOutP": "ANOVA p-value of the output-length effect on log B",
    "BurstInP": "ANOVA p-value of the input-length effect on log B",
    "BurstOutRobustP": "ANOVA p-value of the output-length effect on log B without Gemma's two anomalous cells",
    "BurstModelRobustP": "ANOVA p-value of the model effect on log B without Gemma's two anomalous cells",
    "BurstShort": "geometric-mean burst factor of classes with short answers (1-100 output tokens)",
    "BurstRest": "geometric-mean burst factor of the other classes",
    "BurstShortRatio": "how much larger B is for short answers than for the rest",
    "BurstShortP": "Mann-Whitney p-value for short answers vs the rest",
    "BurstPaperExample": "burst factor implied by the paper's introductory example (1,400 req/min vs 30,000 req/30 min)",
    "BurstMixN": "number of mix designs measured with the same composition in both MIT and MST",
    "BurstMixErr": "mean excess of the measured burst factor of mixes over the one predicted from their classes",
    "BurstMixWithin": "share of those mixes whose measured B is within +-15 % of the prediction",
    "BurstEquivMin": "smallest posterior probability, over model pairs, that two models' burst factors are equivalent within +-10 %",
    "BurstPairMaxDiff": "largest posterior-median difference between the burst factors of two models",
    "BurstPairCi": "largest distance from 1 of the 95 % credible bounds of the ratio between two models' burst factors",
    # token bucket
    "TbWindow": "MIT window W in minutes used to characterise bursts",
    "TbDepth": "token-bucket depth b/s in minutes of refill, b = (B-1) W, with the typical B",
    "TbDepthSafe": "token-bucket depth in minutes of refill with the conservative B_safe",
    "TbDepthSmall": "token-bucket depth in minutes of refill for plans of requests up to 300 tokens",
    "TbBSafe": "conservative burst factor B_safe: 10th percentile over classes (covers 90 % of them)",
    "TbBSmall": "median burst factor of classes up to 300 input and output tokens (the paper's plans)",
    "TbRho": "oversubscription ratio rho used in the paper's example",
    "TbPhiMax": "largest share of the allocation that may burst at once at rho = TbRho: phi <= (B/rho - 1)/(B - 1)",
    "TbRhoMaxHalf": "largest burst-safe oversubscription ratio if half of the allocation bursts at once: rho <= B/(1 + phi(B-1))",
    "TbRhoMaxQuarter": "largest burst-safe oversubscription ratio if a quarter of the allocation bursts at once",
    "TbPaperRatio": "burst-to-sustained rate ratio implied by Table 3 of the paper (Basic plan)",
    "TbBasicBurstTwo": "burst allowance of the paper's Basic plan (50 req/30 min) derived from B, in requests per 2 minutes",
    "TbBasicDepth": "token-bucket depth of the Basic plan derived from B, in requests",
    "TbProBurstTwo": "burst allowance of the paper's Pro plan (175 req/30 min) derived from B, in requests per 2 minutes",
    "TbProDepth": "token-bucket depth of the Pro plan derived from B, in requests",
}

PATTERNS = [
    (r"SdMix(MIT|MST)", lambda k: f"posterior SD of the design effect (departure of a mix design from the harmonic law), {TEST[k]}, as %"),
    (r"SdRun(MIT|MST)", lambda k: f"posterior SD between repeated runs of the same mix design, {TEST[k]}, as %"),
    (r"SdRep(MIT|MST)", lambda k: f"posterior SD between repeated runs of the same pure class, {TEST[k]}, as %"),
    (r"Band(MIT|MST)", lambda k: f"half-width of the 90 % planning band around the harmonic prediction, {TEST[k]}"),
    (r"Mae(MIT|MST)", lambda k: f"mean absolute error of the harmonic prediction per mix design, {TEST[k]}"),
    (r"BiasDesign(MIT|MST)", lambda k: f"mean departure from the harmonic law per mix design, {TEST[k]}"),
    (r"WithinTen(MIT|MST)", lambda k: f"share of mix designs predicted within +-10 %, {TEST[k]}"),
    (r"WithinTen(MIT|MST)Light", lambda k: f"share of mix designs without the heaviest class predicted within +-10 %, {TEST[k]}"),
    (r"WithinTen(MIT|MST)Heavy", lambda k: f"share of mix designs with the heaviest class predicted within +-10 %, {TEST[k]}"),
    (r"Bias(DeepSeek|Gemma|Llama)(MIT|MST)", lambda m, k: f"Bayesian bias delta of {MODEL[m]} mixes w.r.t. the harmonic law, {TEST[k]}"),
    (r"Heavy(DeepSeek|Gemma|Llama)(MIT|MST)", lambda m, k: f"mean departure from the harmonic law of {MODEL[m]} mix designs containing the heaviest class (600-1000 in, 1000-1500 out), {TEST[k]}"),
    (r"Burst(DeepSeek|Gemma|Llama)", lambda m: f"median burst factor B = MIT/MST of {MODEL[m]} over its 20 classes (Bayesian when available)"),
    (r"Burst(DeepSeek|Gemma|Llama)Lo", lambda m: f"lower bound of the 95 % credible interval of {MODEL[m]}'s median burst factor"),
    (r"Burst(DeepSeek|Gemma|Llama)Hi", lambda m: f"upper bound of the 95 % credible interval of {MODEL[m]}'s median burst factor"),
    (r"BurstMax(DeepSeek|Gemma|Llama)", lambda m: f"largest burst factor among {MODEL[m]}'s classes"),
    (r"BurstOnBand(DeepSeek|Gemma|Llama)", lambda m: f"share of {MODEL[m]}'s classes with B within +-15 % of its median"),
    (r"TbSkMax(DeepSeek|Gemma|Llama)", lambda m: f"SK_max of {MODEL[m]}: largest MST in its capacity matrix, req/min (1 K per request of that class)"),
    (r"TbThrottle(DeepSeek|Gemma|Llama)", lambda m: f"throttling threshold Theta = B * SK_max of {MODEL[m]}, sustainable units per minute averaged over W"),
]


def describe(key):
    if key in STATIC:
        return STATIC[key]
    for pat, fn in PATTERNS:
        m = re.fullmatch(pat, key)
        if m:
            return fn(*m.groups())
    raise KeyError(f"macro \\scale{key} has no description in analysis/macro_docs.py")
