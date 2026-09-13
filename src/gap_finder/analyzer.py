from collections import defaultdict
import json
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from src.agent.cohere_client import CohereClient
from src.common.logging import setup_logger

logger = setup_logger("hermes.gap_finder")


class ResearchGapAnalyzer:
    """Open-source literature gap finder using scikit-learn clustering, networkx graph analysis, and Cohere synthesis."""

    def __init__(self, cohere_client: Optional[CohereClient] = None) -> None:
        self.cohere = cohere_client or CohereClient()

    async def analyze_gaps(
        self,
        papers: List[Dict[str, Any]],
        project_goal: str = "",
        min_cluster_size: int = 2,
    ) -> Dict[str, Any]:
        """Perform comprehensive topic clustering, citation graph structural analysis, and trend gap detection."""
        if not papers:
            return {
                "clusters": [],
                "underexplored_clusters": [],
                "bridge_gaps": [],
                "synthesized_gaps": ["Library is currently empty. Ingest literature to enable gap analysis."],
                "proposed_experiments": [],
                "recommended_searches": ["survey recent advances in literature"],
            }

        logger.info(f"Running gap analysis on {len(papers)} papers...")

        # 1. Topic Clustering using scikit-learn TF-IDF + Clustering
        clusters = self._cluster_topics(papers, n_clusters=min(max(len(papers) // 2, 2), 6))

        # 2. Trend Analysis using pandas/numpy (velocity & recency)
        underexplored = self._analyze_trends(clusters, papers)

        # 3. Network Graph Analysis using NetworkX
        bridges = self._analyze_graph_bridges(papers)

        # 4. Extract Missing Baselines, Datasets & Metrics from notes
        missing_signals = self._extract_missing_signals(papers)

        # 5. Cohere Synthesis for Final Research Gap Statements
        synthesized = await self._synthesize_gap_insights(
            project_goal=project_goal,
            clusters=clusters,
            underexplored=underexplored,
            bridges=bridges,
            missing_signals=missing_signals,
        )

        return {
            "total_papers_analyzed": len(papers),
            "clusters": clusters,
            "underexplored_clusters": underexplored,
            "bridge_gaps": bridges,
            "missing_signals": missing_signals,
            "synthesized_gaps": synthesized.get("top_gaps", []),
            "proposed_experiments": synthesized.get("proposed_experiments", []),
            "recommended_searches": synthesized.get("recommended_searches", []),
        }

    def _cluster_topics(self, papers: List[Dict[str, Any]], n_clusters: int) -> List[Dict[str, Any]]:
        """Cluster papers by text content using scikit-learn TF-IDF."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans

        corpus = [f"{p.get('title', '')} {p.get('abstract', '')}" for p in papers]

        if len(papers) < 2:
            return [{
                "cluster_id": 0,
                "label": "General Literature",
                "keywords": ["foundational"],
                "paper_keys": [papers[0].get("bibtex_key", "Paper1")],
                "size": 1,
            }]

        k = min(n_clusters, len(papers))
        vectorizer = TfidfVectorizer(stop_words="english", max_features=500)
        X = vectorizer.fit_transform(corpus)

        kmeans = KMeans(n_clusters=k, random_state=42, n_init=5)
        labels = kmeans.fit_predict(X)

        feature_names = np.array(vectorizer.get_feature_names_out())
        clusters = []

        for i in range(k):
            indices = np.where(labels == i)[0]
            if len(indices) == 0:
                continue

            center = kmeans.cluster_centers_[i]
            top_keyword_indices = center.argsort()[-4:][::-1]
            keywords = [feature_names[idx] for idx in top_keyword_indices if idx < len(feature_names)]
            cluster_label = " & ".join(keywords[:2]).title() if keywords else f"Cluster {i}"

            cluster_papers = [papers[idx].get("bibtex_key", f"Paper{idx}") for idx in indices]
            clusters.append({
                "cluster_id": i,
                "label": cluster_label,
                "keywords": keywords,
                "paper_keys": cluster_papers,
                "size": len(cluster_papers),
            })

        return clusters

    def _analyze_trends(self, clusters: List[Dict[str, Any]], papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify underexplored clusters (low volume but positive publication trend / recent activity)."""
        paper_year_map = {p.get("bibtex_key"): p.get("year") or 2022 for p in papers}
        underexplored = []

        for c in clusters:
            years = [paper_year_map.get(k, 2022) for k in c["paper_keys"]]
            avg_year = float(np.mean(years)) if years else 2022.0
            # Clusters that are small (<= 3 papers) but recent (avg year >= 2023)
            is_emerging = (c["size"] <= 4) and (avg_year >= 2023.0)
            if is_emerging:
                underexplored.append({
                    "cluster_id": c["cluster_id"],
                    "label": c["label"],
                    "paper_count": c["size"],
                    "average_year": round(avg_year, 1),
                    "insight": f"Emerging sub-topic with high recency ({avg_year:.0f}) but limited paper coverage in current library.",
                    "representative_papers": c["paper_keys"],
                })

        return underexplored

    def _analyze_graph_bridges(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Use NetworkX to construct literature similarity graph and identify structural bridge gaps."""
        try:
            import networkx as nx
        except ImportError:
            return []

        G = nx.Graph()
        for p in papers:
            bkey = p.get("bibtex_key", "Key")
            G.add_node(bkey, title=p.get("title", ""), year=p.get("year", 2024))

        # Add edges between papers with common keywords / venues
        for i in range(len(papers)):
            p1 = papers[i]
            tokens1 = set(p1.get("title", "").lower().split())
            for j in range(i + 1, len(papers)):
                p2 = papers[j]
                tokens2 = set(p2.get("title", "").lower().split())
                overlap = len(tokens1.intersection(tokens2))
                if overlap >= 2:
                    G.add_edge(p1.get("bibtex_key"), p2.get("bibtex_key"), weight=overlap)

        if len(G.edges()) == 0:
            return []

        # Betweenness centrality: identifying bridge nodes
        centrality = nx.betweenness_centrality(G)
        sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)

        bridges = []
        for node, score in sorted_nodes[:3]:
            if score > 0.0:
                neighbors = list(G.neighbors(node))
                bridges.append({
                    "bridge_paper": node,
                    "centrality_score": round(score, 3),
                    "connected_nodes": neighbors[:3],
                    "structural_insight": f"Paper '{node}' acts as an interdisciplinary bridge between disparate clusters.",
                })

        return bridges

    def _extract_missing_signals(self, papers: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Collect explicit limitations, benchmark datasets, and evaluation metrics reported in paper notes."""
        limitations = []
        datasets = set()
        metrics = set()

        for p in papers:
            note_list = []
            if p.get("note"):
                note_list.append(p["note"])
            if p.get("notes"):
                if isinstance(p["notes"], list):
                    note_list.extend(p["notes"])
                elif isinstance(p["notes"], dict):
                    note_list.append(p["notes"])

            for note in note_list:
                if note.get("limitations"):
                    limitations.append(note["limitations"])
                for d in note.get("datasets", []):
                    datasets.add(d)
                for m in note.get("metrics", []):
                    metrics.add(m)

        ds_list = list(datasets)[:6]
        met_list = list(metrics)[:6]
        lim_list = limitations[:5]

        return {
            "reported_limitations": lim_list,
            "benchmark_datasets": ds_list,
            "evaluation_metrics": met_list,
            "limitations": lim_list,
            "datasets": ds_list,
            "metrics": met_list,
        }

    async def _synthesize_gap_insights(
        self,
        project_goal: str,
        clusters: List[Dict[str, Any]],
        underexplored: List[Dict[str, Any]],
        bridges: List[Dict[str, Any]],
        missing_signals: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Synthesize concrete research gap statements and experiment designs using Cohere Chat."""
        context = f"""Research Goal: {project_goal or 'Advancing scientific state of the art'}

Topic Clusters Identified:
{json.dumps(clusters, indent=2)}

Underexplored / Emerging Clusters:
{json.dumps(underexplored, indent=2)}

Bridge Papers / Structural Graph Gaps:
{json.dumps(bridges, indent=2)}

Extracted Literature Limitations:
{json.dumps(missing_signals.get('reported_limitations', []), indent=2)}
"""
        system_prompt = """You are a Principal Scientific Director specializing in discovering high-impact research gaps.
Analyze the provided topic clusters, graph bridges, and reported limitations to formulate:
1. Top 3-5 concrete scientific research gaps (unexplored problems, contested claims, or missing evaluations).
2. Recommended experimental plans with ablations to resolve these gaps.
3. 2-3 targeted search queries to find adjacent literature.

Output valid JSON matching this schema:
{
  "top_gaps": ["gap 1 with rationale", "gap 2 with rationale", ...],
  "proposed_experiments": ["concrete experiment plan 1", "concrete experiment plan 2"],
  "recommended_searches": ["search query 1", "search query 2"]
}
"""
        try:
            content = await self.cohere.chat(
                message=context,
                system_prompt=system_prompt,
                temperature=0.2,
                json_response=True,
            )
            return json.loads(content)
        except Exception as e:
            logger.warning(f"Cohere gap synthesis failed ({e}). Returning heuristic gap statements.")
            return {
                "top_gaps": [
                    "Gap 1: Limited comparative benchmarks across emerging clusters and legacy baselines.",
                    "Gap 2: Lack of empirical validation under resource-constrained / edge runtime conditions.",
                ],
                "proposed_experiments": [
                    "Conduct cross-dataset ablation evaluating computational efficiency vs baseline accuracy."
                ],
                "recommended_searches": [
                    "cross-benchmark evaluation limitations",
                    "ablation studies on empirical efficiency"
                ]
            }
