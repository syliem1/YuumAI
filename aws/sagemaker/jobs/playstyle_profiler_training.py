import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import silhouette_score
import joblib
import json
import os 
from typing import Dict, List
import argparse

class PlaystyleProfiler:
    """
    Machine Learning model for player playstyle profiling and archetype classification
    Maps playstyles to 13 League of Legends regions based on thematic characteristics
    """
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.kmeans = None
        self.pca = None
        self.archetype_names = {}
        self.feature_importance = {}
        
        # Region characteristics for mapping
        self.region_themes = {
            'Bandle City': ['whimsical', 'unpredictable', 'mobile', 'creative'],
            'Bilgewater': ['aggressive', 'opportunistic', 'risky', 'gold-focused'],
            'Demacia': ['honorable', 'protective', 'teamfight', 'consistent'],
            'Ionia': ['balanced', 'harmonious', 'skillful', 'adaptable'],
            'Ixtal': ['jungle-focused', 'elemental', 'objective-control', 'hidden'],
            'Noxus': ['dominant', 'aggressive', 'conquest', 'powerful'],
            'Piltover': ['efficient', 'innovative', 'calculated', 'wealthy'],
            'Shadow Isles': ['draining', 'persistent', 'sustain', 'deaths-dance'],
            'Shurima': ['late-game', 'scaling', 'empire-building', 'patient'],
            'Targon': ['supportive', 'protective', 'vision', 'celestial'],
            'The Freljord': ['tanky', 'survival', 'cc-heavy', 'enduring'],
            'The Void': ['consuming', 'chaotic', 'damage-focused', 'relentless'],
            'Zaun': ['experimental', 'high-risk', 'damage-over-time', 'chaotic']
        }
        
    def engineer_behavioral_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Creates region-themed features from the PRE-AGGREGATED match statistics
        """
        
        features = df.copy()
        
        # Bandle City
        features['bandle'] = (
            features['avg_outnumbered_kills'] * 0.4 +
            features['avg_kda'] * 0.3 +
            features['avg_vision_score'] / 40.0 * 0.3 
        )
        
        # Bilgewater
        features['bilgewater'] = (
            features['avg_gpm'] / 400 * 0.4 +
            features['avg_solo_kills'] * 0.3 +
            features['avg_kills_near_tower'] * 0.3
        )
        
        # Demacia 
        features['demacia'] = (
            features['avg_kill_participation'] * 0.4 +
            features['avg_team_damage_pct'] * 0.3 +
            features['avg_shields_on_teammates'] / 500 * 0.3
        )
        
        # Ionia
        features['ionia'] = (
            features['avg_kda'] / 4 * 0.3 +
            (features['avg_kill_participation'] * features['avg_cs_per_min'] / 7) * 0.4 +
            features['avg_vision_score'] / 40 * 0.3
        )
        
        # Ixtal 
        features['ixtal'] = (
            features['avg_objective_damage'] / 10000 * 0.4 +
            features['avg_dragon_takedowns'] * 0.3 +
            features['avg_herald_takedowns'] * 0.3
        )
        
        # Noxus
        features['noxus'] = (
            features['avg_dpm'] / 600 * 0.4 +
            features['avg_early_gold_adv'] / 500 * 0.3 +
            features['avg_turret_kills'] * 0.3
        )
        
        # Piltover
        features['piltover'] = (
            features['avg_gpm'] / 400 * 0.4 +               
            features['avg_cs_per_min'] / 7 * 0.3 +
            features['cs_consistency'] * 0.3              
        )
        
        # Shadow Isles
        features['shadow_isles'] = (
            features['avg_heals_on_teammates'] / 1000 * 0.4 + 
            features['avg_longest_alive'] / 600 * 0.3 + 
            features['avg_kda'] * 0.3                          
        )
        
        # Shurima
        features['shurima'] = (
            features['avg_cs_per_min'] / 7 * 0.5 +
            features['avg_gpm'] * 0.5                       
        )
        
        # Targon
        features['targon'] = (
            features['avg_vision_score'] / 40 * 0.4 +
            features['avg_shields_on_teammates'] / 500 * 0.3 +
            features['avg_heals_on_teammates'] / 1000 * 0.3
        )
        
        # Freljord
        features['freljord'] = (
            features['avg_cc_time'] / 20 * 0.4 +
            features['avg_time_dead'] / 60 * -0.3 +
            (1 / (features['death_consistency'] + 0.1)) * 0.3 
        )
        
        # The Void
        features['void'] = (
            features['avg_dpm'] / 600 * 0.4 +
            features['avg_team_damage_pct'] * 0.4 +
            features['avg_solo_kills'] * 0.2
        )
        
        # Zaun
        features['zaun'] = (
            (1 / (features['death_consistency'] + 0.1)) * -0.3 + 
            features['avg_outnumbered_kills'] * 0.4 +
            features['avg_pick_kills'] * 0.3
        )
        
        return features
    
    def train_clustering_model(self, df: pd.DataFrame, n_clusters: int = 13):
        """
        Trains K-means clustering for region-based archetype identification
        """
        
        # Regional feature set for clustering
        clustering_features = [
            # Regional identity features
            'bandle',
            'bilgewater',
            'demacia',
            'ionia',
            'ixtal',
            'noxus',
            'piltover',
            'shadow_isles',
            'shurima',
            'targon',
            'freljord',
            'void',
            'zaun',
            # Supporting metrics
            'avg_dpm',
            'avg_gpm',
            'avg_kill_participation',
            'avg_kda',
            'avg_vision_score',
            'avg_cs_per_min',
            'avg_team_damage_pct'
        ]
        
        valid_features = [col for col in clustering_features if col in df.columns]
        print(f"Using {len(valid_features)} features for clustering.")
        print(f"Regional features: {[f for f in valid_features if not f.startswith('avg_')]}")
        
        X = df[valid_features].fillna(0)
        
        # Standardize features
        X_scaled = self.scaler.fit_transform(X)
        
        # Apply PCA - preserve more variance for 13 clusters
        self.pca = PCA(n_components=min(13, len(valid_features)))
        X_pca = self.pca.fit_transform(X_scaled)
        
        # Train K-means with 13 clusters (one per region)
        self.kmeans = KMeans(
            n_clusters=n_clusters,
            init='k-means++',
            n_init=20,  # More initializations for better clustering
            max_iter=500,
            random_state=42
        )
        
        clusters = self.kmeans.fit_predict(X_pca)
        df['cluster'] = clusters
        
        try:
            score = silhouette_score(X_pca, clusters)
        except ValueError:
            score = 0
        
        self.archetype_names = self._assign_region_names(df, valid_features)
        
        self._calculate_feature_importance(df, valid_features)
        
        return df, score, X_pca, valid_features
    
    def _assign_region_names(self, df: pd.DataFrame, features: list) -> Dict:
        """
        Assigns region names to clusters based on regional feature dominance
        """
        archetype_names = {}
        
        # Regional features in order
        regional_features = [
            'bandle', 'bilgewater', 'demacia', 'ionia',
            'ixtal', 'noxus', 'piltover', 'shadow_isles',
            'shurima', 'targon', 'freljord',
            'void', 'zaun'
        ]
        
        # Region names corresponding to features
        region_names = [
            'Bandle City', 'Bilgewater', 'Demacia', 'Ionia', 'Ixtal',
            'Noxus', 'Piltover', 'Shadow Isles', 'Shurima', 'Targon',
            'The Freljord', 'The Void', 'Zaun'
        ]
        
        # Calculate which region each cluster represents
        global_means = df[[f for f in regional_features if f in features]].mean()
        
        assigned_regions = set()
        cluster_region_scores = {}
        
        for cluster_id in range(df['cluster'].nunique()):
            cluster_data = df[df['cluster'] == cluster_id]
            cluster_means = cluster_data[[f for f in regional_features if f in features]].mean()
            
            # Calculate relative strength for each region
            relative_scores = (cluster_means - global_means) / (global_means + 1e-6)
            
            # Store scores for this cluster
            cluster_region_scores[cluster_id] = relative_scores
        
        # Assign regions based on best fit (greedy assignment)
        for _ in range(df['cluster'].nunique()):
            best_match = None
            best_score = -float('inf')
            best_cluster = None
            
            for cluster_id in range(df['cluster'].nunique()):
                if cluster_id in [k for k, v in archetype_names.items() if 'region_assigned' in v]:
                    continue
                    
                scores = cluster_region_scores[cluster_id]
                
                for region_feat, region_name in zip(regional_features, region_names):
                    if region_name in assigned_regions or region_feat not in scores.index:
                        continue
                    
                    if scores[region_feat] > best_score:
                        best_score = scores[region_feat]
                        best_match = region_name
                        best_cluster = cluster_id
            
            if best_match:
                cluster_data = df[df['cluster'] == best_cluster]
                assigned_regions.add(best_match)

                profile_themes = self.region_themes.get(best_match, [])
                profile_text = ", ".join(profile_themes).title()
                
                archetype_names[best_cluster] = {
                    'name': best_match,
                    'region_assigned': True,
                    'count': len(cluster_data),
                    'win_rate': cluster_data['win_rate'].mean(),
                    'avg_kda': cluster_data['avg_kda'].mean(),
                    'avg_gpm': cluster_data['avg_gpm'].mean(),
                    'dominant_score': float(best_score),
                    'profile': profile_text
                }
        
        return archetype_names
    
    def _calculate_feature_importance(self, df: pd.DataFrame, features: list):
        X = df[features].fillna(0)
        y = df['cluster']
        
        if len(X) < 50:
            print("Not enough samples for feature importance calculation.")
            self.feature_importance = {}
            return

        rf = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=15)
        rf.fit(X, y)
        
        self.feature_importance = dict(zip(features, rf.feature_importances_))
    
    def plot_clustering_results(self, df: pd.DataFrame, X_pca: np.ndarray, 
                                valid_features: list, output_path: str):
        """
        Creates comprehensive visualization of clustering results
        """
        # Import matplotlib here to avoid early loading issues
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.cm as cm
        
        print("Generating visualizations...")
        
        # Set style
        plt.style.use('default')
        plt.rcParams['figure.facecolor'] = 'white'
        plt.rcParams['axes.grid'] = True
        plt.rcParams['grid.alpha'] = 0.3
        
        # Create output directory for plots
        plots_dir = os.path.join(output_path, "plots")
        os.makedirs(plots_dir, exist_ok=True)
        
        # 1. PCA Scatter Plot with Clusters
        fig, ax = plt.subplots(figsize=(14, 10))
        scatter = ax.scatter(X_pca[:, 0], X_pca[:, 1], 
                            c=df['cluster'], 
                            cmap='tab20', 
                            alpha=0.6, 
                            s=50)
        
        # Add cluster centers (already in PCA space)
        centers_pca = self.kmeans.cluster_centers_
        ax.scatter(centers_pca[:, 0], centers_pca[:, 1], 
                  c='red', marker='X', s=400, 
                  edgecolors='black', linewidths=2,
                  label='Region Centers')
        
        ax.set_xlabel(f'PC1 ({self.pca.explained_variance_ratio_[0]:.1%} variance)', fontsize=12)
        ax.set_ylabel(f'PC2 ({self.pca.explained_variance_ratio_[1]:.1%} variance)', fontsize=12)
        ax.set_title('Player Playstyle Regions of Runeterra', fontsize=16, fontweight='bold')
        
        # Add legend with region names
        handles, labels = scatter.legend_elements()
        legend_labels = [self.archetype_names.get(int(label.split('{')[1].split('}')[0]), {}).get('name', f'Cluster {label}')
                        for label in labels]
        ax.legend(handles, legend_labels, title="Regions", 
                 bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
        
        plt.tight_layout()
        plt.savefig(os.path.join(plots_dir, 'pca_clusters.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. Region Size Distribution
        fig, ax = plt.subplots(figsize=(14, 7))
        cluster_counts = df['cluster'].value_counts().sort_index()
        region_names = [self.archetype_names.get(i, {}).get('name', f'Cluster {i}') 
                       for i in cluster_counts.index]
        
        bars = ax.bar(range(len(cluster_counts)), cluster_counts.values, 
                     color=plt.cm.tab20(range(len(cluster_counts))))
        ax.set_xticks(range(len(cluster_counts)))
        ax.set_xticklabels(region_names, rotation=45, ha='right')
        ax.set_ylabel('Number of Players', fontsize=12)
        ax.set_title('Distribution of Players Across Runeterra Regions', fontsize=14, fontweight='bold')
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}',
                   ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        plt.savefig(os.path.join(plots_dir, 'region_distribution.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
        # 3. Feature Importance Plot
        if self.feature_importance:
            fig, ax = plt.subplots(figsize=(12, 10))
            importances = pd.Series(self.feature_importance).sort_values(ascending=True)
            
            colors = plt.cm.viridis(np.linspace(0, 1, len(importances)))
            importances.plot(kind='barh', ax=ax, color=colors)
            ax.set_xlabel('Importance Score', fontsize=12)
            ax.set_title('Feature Importance for Region Classification', 
                        fontsize=14, fontweight='bold')
            ax.set_yticklabels([label.get_text().replace('_', ' ').title() 
                               for label in ax.get_yticklabels()])
            
            plt.tight_layout()
            plt.savefig(os.path.join(plots_dir, 'feature_importance.png'), dpi=300, bbox_inches='tight')
            plt.close()
        
        # 4. Heatmap of Region Characteristics
        fig, ax = plt.subplots(figsize=(16, 10))
        
        # Calculate mean features for each cluster
        cluster_profiles = []
        for cluster_id in sorted(df['cluster'].unique()):
            cluster_data = df[df['cluster'] == cluster_id]
            profile = cluster_data[valid_features].mean()
            cluster_profiles.append(profile)
        
        cluster_profiles_df = pd.DataFrame(cluster_profiles)
        cluster_profiles_df.index = [self.archetype_names.get(i, {}).get('name', f'Cluster {i}')
                                     for i in sorted(df['cluster'].unique())]
        
        # Normalize for better visualization
        cluster_profiles_normalized = (cluster_profiles_df - cluster_profiles_df.mean()) / cluster_profiles_df.std()
        
        # Create heatmap
        im = ax.imshow(cluster_profiles_normalized.T, cmap='RdYlGn', aspect='auto', 
                      vmin=-2, vmax=2, interpolation='nearest')
        ax.set_xticks(range(len(cluster_profiles_normalized)))
        ax.set_xticklabels(cluster_profiles_normalized.index, rotation=45, ha='right', fontsize=9)
        ax.set_yticks(range(len(cluster_profiles_normalized.columns)))
        ax.set_yticklabels(cluster_profiles_normalized.columns, fontsize=8)
        plt.colorbar(im, ax=ax, label='Normalized Score')
        
        ax.set_xlabel('Region', fontsize=12)
        ax.set_ylabel('Feature', fontsize=12)
        ax.set_title('Regional Playstyle Profiles', fontsize=14, fontweight='bold')
        ax.set_yticklabels([label.get_text().replace('_', ' ').title() 
                           for label in ax.get_yticklabels()], rotation=0)
        
        plt.tight_layout()
        plt.savefig(os.path.join(plots_dir, 'region_heatmap.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
        # 5. Win Rate by Region
        fig, ax = plt.subplots(figsize=(14, 7))
        win_rates = [self.archetype_names.get(i, {}).get('win_rate', 0.5) * 100 
                    for i in sorted(df['cluster'].unique())]
        region_names = [self.archetype_names.get(i, {}).get('name', f'Cluster {i}')
                       for i in sorted(df['cluster'].unique())]
        
        bars = ax.bar(range(len(win_rates)), win_rates,
                     color=plt.cm.RdYlGn(np.array(win_rates) / 100))
        ax.axhline(y=50, color='black', linestyle='--', linewidth=1, alpha=0.5, label='50% Win Rate')
        ax.set_xticks(range(len(region_names)))
        ax.set_xticklabels(region_names, rotation=45, ha='right')
        ax.set_ylabel('Win Rate (%)', fontsize=12)
        ax.set_title('Average Win Rate by Region', fontsize=14, fontweight='bold')
        ax.set_ylim([min(win_rates) - 5, max(win_rates) + 5])
        ax.legend()
        
        # Add value labels on bars
        for bar, wr in zip(bars, win_rates):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{wr:.1f}%',
                   ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        plt.savefig(os.path.join(plots_dir, 'winrate_by_region.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
        # 6. PCA Explained Variance
        fig, ax = plt.subplots(figsize=(12, 7))
        variance_ratio = self.pca.explained_variance_ratio_
        cumulative_variance = np.cumsum(variance_ratio)
        
        ax.bar(range(1, len(variance_ratio) + 1), variance_ratio, 
              alpha=0.6, label='Individual Variance')
        ax.plot(range(1, len(cumulative_variance) + 1), cumulative_variance, 
               'ro-', linewidth=2, label='Cumulative Variance')
        
        ax.set_xlabel('Principal Component', fontsize=12)
        ax.set_ylabel('Explained Variance Ratio', fontsize=12)
        ax.set_title('PCA Explained Variance', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(plots_dir, 'pca_variance.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
        # 7. Regional Feature Radar Charts (Top 3 Most Populous Regions)
        top_3_clusters = df['cluster'].value_counts().head(3).index.tolist()
        
        fig, axes = plt.subplots(1, 3, figsize=(20, 7), subplot_kw=dict(projection='polar'))
        
        # Use regional identity features
        regional_features = ['bandle', 'bilgewater', 'demacia', 
                           'ionia', 'ixtal', 'noxus']
        regional_features = [f for f in regional_features if f in valid_features][:6]
        
        angles = np.linspace(0, 2 * np.pi, len(regional_features), endpoint=False).tolist()
        angles += angles[:1]
        
        for idx, cluster_id in enumerate(top_3_clusters):
            ax = axes[idx]
            cluster_data = df[df['cluster'] == cluster_id]
            values = cluster_data[regional_features].mean().tolist()
            values += values[:1]
            
            region_name = self.archetype_names.get(cluster_id, {}).get('name', f'Cluster {cluster_id}')
            
            ax.plot(angles, values, 'o-', linewidth=2, label=region_name)
            ax.fill(angles, values, alpha=0.25)
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels([f.replace('_', ' ').replace('bandle', 'Bandle').replace('bilgewater', 'Bilgewater')
                               .replace('demacia', 'Demacia').replace('ionia', 'Ionia')
                               .replace('ixtal', 'Ixtal').replace('noxus', 'Noxus').title() 
                               for f in regional_features], size=8)
            ax.set_title(region_name, fontsize=13, fontweight='bold', pad=20)
            ax.grid(True)
        
        plt.tight_layout()
        plt.savefig(os.path.join(plots_dir, 'region_radar_charts.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"All visualizations saved to {plots_dir}/")
    
    def save_model(self, output_path: str):
        os.makedirs(output_path, exist_ok=True)
        
        model_artifacts = {
            'scaler': self.scaler,
            'kmeans': self.kmeans,
            'pca': self.pca,
            'archetype_names': self.archetype_names,
            'feature_importance': self.feature_importance
        }
        
        joblib.dump(model_artifacts, os.path.join(output_path, "playstyle_profiler.pkl"))
        
        with open(os.path.join(output_path, "archetypes.json"), 'w') as f:
            json.dump(self.archetype_names, f, indent=2, default=lambda x: x.item() if isinstance(x, np.generic) else x)

# SageMaker Training Script
def train_on_sagemaker():
    print("Starting SageMaker training script...")
    print("Training Runeterra Regional Playstyle Classifier")
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--n-clusters', type=int, default=13)
    parser.add_argument('--train', type=str, default=os.environ.get('SM_CHANNEL_TRAIN'))
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR'))
    
    args, _ = parser.parse_known_args()
    
    print(f"Training data path: {args.train}")
    print(f"Model output path: {args.model_dir}")
    print(f"Number of regions: {args.n_clusters}")
    
    training_file_path = os.path.join(args.train, "player_features_train.parquet")
    
    if not os.path.exists(training_file_path):
        print(f"Error: File not found at {training_file_path}")
        print("Listing files in training directory:")
        print(os.listdir(args.train))
        raise FileNotFoundError(f"File not found: {training_file_path}")
        
    print("Loading data...")
    df = pd.read_parquet(training_file_path)
    print(f"Loaded {len(df)} rows.")
    
    profiler = PlaystyleProfiler()
    
    print("Engineering regional features...")
    df_with_features = profiler.engineer_behavioral_features(df)
    
    print(f"Training clustering model with {args.n_clusters} regions...")
    df_clustered, silhouette_avg, X_pca, valid_features = profiler.train_clustering_model(
        df_with_features, n_clusters=args.n_clusters
    )
    print(f"Clustering complete. Silhouette Score: {silhouette_avg}")
    
    # Print region assignments
    print("\n" + "="*60)
    print("REGION ASSIGNMENTS:")
    print("="*60)
    for cluster_id in sorted(profiler.archetype_names.keys()):
        info = profiler.archetype_names[cluster_id]
        print(f"{info['name']:20s} | Players: {info['count']:5d} | Win Rate: {info['win_rate']*100:5.2f}%")
    print("="*60 + "\n")
    
    print(f"Saving model to {args.model_dir}...")
    profiler.save_model(args.model_dir)

    validation_metrics = {
        'silhouette_score': silhouette_avg,
        'n_clusters': args.n_clusters,
        'n_samples': len(df),
        'regions': {k: v['name'] for k, v in profiler.archetype_names.items()}
    }
    
    metrics_path = os.path.join(args.model_dir, "validation_metrics.json")
    with open(metrics_path, 'w') as f:
        json.dump(validation_metrics, f, indent=2)
    
    print("Training completed successfully")
    print(f"Model artifacts saved to {args.model_dir}")

if __name__ == "__main__":
    train_on_sagemaker()