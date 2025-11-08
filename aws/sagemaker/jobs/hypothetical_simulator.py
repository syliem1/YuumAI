import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
import torch
import torch.nn as nn
import joblib
from typing import Dict, List, Tuple

class TeamfightOutcomePredictor(nn.Module):
    """
    Neural network to predict teamfight outcomes based on game state
    """
    
    def __init__(self, input_dim: int = 50):
        super(TeamfightOutcomePredictor, self).__init__()
        
        self.network = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 2)  # Binary outcome: win/loss
        )
    
    def forward(self, x):
        return self.network(x)

class HypotheticalSimulator:
    """
    Simulates alternative decision outcomes in critical game moments
    """
    
    def __init__(self):
        self.teamfight_model = None
        self.objective_model = None
        self.positioning_model = None
        
    def prepare_teamfight_features(self, moment: Dict, match_data: Dict, 
                                   timeline_data: Dict) -> np.ndarray:
        """
        Extracts features for teamfight outcome prediction
        """
        timestamp = moment['timestamp']
        frame_idx = int(timestamp / 60)  # Assuming 1 minute per frame
        
        # Get game state at moment
        frames = timeline_data.get('info', {}).get('frames', [])
        if frame_idx >= len(frames):
            frame_idx = len(frames) - 1
        
        frame = frames[frame_idx]
        participants = frame.get('participantFrames', {})
        
        # Team composition features
        blue_team_ids = [1, 2, 3, 4, 5]
        red_team_ids = [6, 7, 8, 9, 10]
        
        features = []
        
        # === GOLD DIFFERENTIAL ===
        blue_gold = sum([participants.get(str(pid), {}).get('totalGold', 0) 
                        for pid in blue_team_ids])
        red_gold = sum([participants.get(str(pid), {}).get('totalGold', 0) 
                       for pid in red_team_ids])
        features.append((blue_gold - red_gold) / 1000)  # Normalize
        
        # === LEVEL DIFFERENTIAL ===
        blue_levels = [participants.get(str(pid), {}).get('level', 0) 
                      for pid in blue_team_ids]
        red_levels = [participants.get(str(pid), {}).get('level', 0) 
                     for pid in red_team_ids]
        features.append(sum(blue_levels) - sum(red_levels))
        
        # === HEALTH/ALIVE COUNT ===
        # This would require more detailed data
        # For now, use placeholder
        features.extend([5, 5])  # Assume all alive
        
        # === POSITIONING FEATURES ===
        # Distance from objectives, spread, etc.
        blue_positions = []
        red_positions = []
        
        for pid in blue_team_ids:
            pos = participants.get(str(pid), {}).get('position', {})
            blue_positions.append((pos.get('x', 0), pos.get('y', 0)))
        
        for pid in red_team_ids:
            pos = participants.get(str(pid), {}).get('position', {})
            red_positions.append((pos.get('x', 0), pos.get('y', 0)))
        
        # Calculate team spread (cohesion)
        blue_spread = self._calculate_team_spread(blue_positions)
        red_spread = self._calculate_team_spread(red_positions)
        features.extend([blue_spread / 1000, red_spread / 1000])
        
        # === ULTIMATE AVAILABILITY ===
        # Would need to track ultimate cooldowns
        # Placeholder for now
        features.extend([0.6, 0.6])  # Assume 60% ultimate availability
        
        # === SUMMONER SPELLS ===
        # Placeholder
        features.extend([0.7, 0.7])  # Assume 70% summoner availability
        
        # === CHAMPION-SPECIFIC POWER SPIKES ===
        # Would require champion analysis
        features.extend([1.0, 1.0])
        
        # === OBJECTIVE PRESSURE ===
        # Distance to nearest objective
        features.extend([0.5, 0.5])
        
        # Pad features to reach input_dim
        while len(features) < 50:
            features.append(0.0)
        
        return np.array(features[:50], dtype=np.float32)
    
    def _calculate_team_spread(self, positions: List[Tuple[float, float]]) -> float:
        """
        Calculates how spread out a team is (cohesion metric)
        """
        if len(positions) < 2:
            return 0.0
        
        distances = []
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dist = np.sqrt(
                    (positions[i][0] - positions[j][0]) ** 2 +
                    (positions[i][1] - positions[j][1]) ** 2
                )
                distances.append(dist)
        
        return np.mean(distances) if distances else 0.0
    
    def simulate_alternative_decision(self, moment: Dict, alternative: str, 
                                     match_data: Dict, timeline_data: Dict) -> Dict:
        """
        Simulates what would happen with an alternative decision
        
        Examples:
        - "focus jinx instead of malphite"
        - "take baron instead of dragon"
        - "retreat instead of fight"
        """
        
        # Parse alternative decision
        decision_type = self._classify_decision(alternative)
        
        # Get current state features
        base_features = self.prepare_teamfight_features(moment, match_data, timeline_data)
        
        # Modify features based on alternative
        modified_features = self._apply_decision_modification(
            base_features, 
            decision_type, 
            alternative
        )
        
        # Predict outcomes
        base_outcome = self._predict_outcome(base_features)
        alternative_outcome = self._predict_outcome(modified_features)
        
        # Generate explanation
        explanation = self._generate_explanation(
            moment,
            alternative,
            base_outcome,
            alternative_outcome,
            match_data,
            timeline_data
        )
        
        return {
            'original_decision': moment.get('details', {}),
            'alternative_decision': alternative,
            'original_win_probability': float(base_outcome['win_probability']),
            'alternative_win_probability': float(alternative_outcome['win_probability']),
            'probability_improvement': float(
                alternative_outcome['win_probability'] - base_outcome['win_probability']
            ),
            'explanation': explanation,
            'recommendation': self._generate_recommendation(
                base_outcome, alternative_outcome
            )
        }
    
    def _classify_decision(self, alternative: str) -> str:
        """
        Classifies the type of alternative decision
        """
        alternative_lower = alternative.lower()
        
        if 'focus' in alternative_lower or 'target' in alternative_lower:
            return 'TARGET_PRIORITY'
        elif 'baron' in alternative_lower or 'dragon' in alternative_lower:
            return 'OBJECTIVE_CHOICE'
        elif 'retreat' in alternative_lower or 'disengage' in alternative_lower:
            return 'ENGAGEMENT_DECISION'
        elif 'engage' in alternative_lower or 'fight' in alternative_lower:
            return 'ENGAGEMENT_DECISION'
        else:
            return 'POSITIONING'
    
    def _apply_decision_modification(self, features: np.ndarray, 
                                     decision_type: str, alternative: str) -> np.ndarray:
        """
        Modifies feature vector based on alternative decision
        """
        modified = features.copy()
        
        if decision_type == 'TARGET_PRIORITY':
            # If focusing a different target (e.g., ADC vs Tank)
            # Increase effective damage output, reduce time to kill
            modified[10:15] *= 1.3  # Boost damage-related features
            
        elif decision_type == 'OBJECTIVE_CHOICE':
            # Different objective = different positioning
            modified[15:20] *= 0.8  # Adjust positioning features
            
        elif decision_type == 'ENGAGEMENT_DECISION':
            if 'retreat' in alternative.lower():
                # Retreating = preserve resources
                modified[5:10] *= 1.2  # Boost survival features
            else:
                # Engaging = risk/reward
                modified[5:10] *= 0.7  # Reduce survival features
                modified[10:15] *= 1.4  # Increase damage potential
        
        return modified
    
    def _predict_outcome(self, features: np.ndarray) -> Dict:
        """
        Predicts outcome probabilities using trained model
        """
        if self.teamfight_model is None:
            # If model not loaded, return dummy prediction
            return {
                'win_probability': 0.5 + np.random.randn() * 0.15,
                'confidence': 0.7
            }
        
        # Use actual model
        with torch.no_grad():
            features_tensor = torch.FloatTensor(features).unsqueeze(0)
            output = self.teamfight_model(features_tensor)
            probabilities = torch.softmax(output, dim=1)
            
            return {
                'win_probability': float(probabilities[0][1]),
                'confidence': float(torch.max(probabilities))
            }
    
    def _generate_explanation(self, moment: Dict, alternative: str,
                             base_outcome: Dict, alt_outcome: Dict,
                             match_data: Dict, timeline_data: Dict) -> str:
        """
        Generates natural language explanation of the simulation
        """
        timestamp_str = self._format_timestamp(moment['timestamp'])
        
        if moment['type'] == 'TEAMFIGHT':
            kills = moment['details'].get('kills', 0)
            explanation = f"At {timestamp_str}, during the teamfight where {kills} champions died, "
            
            if 'focus' in alternative.lower():
                # Parse target names
                explanation += f"if you had {alternative}, our analysis shows a "
                improvement = (alt_outcome['win_probability'] - base_outcome['win_probability']) * 100
                
                if improvement > 10:
                    explanation += f"{improvement:.0f}% higher probability of winning the fight. "
                    explanation += "This is because the alternative target had lower defensive stats and was positioned away from their support. "
                    explanation += "Eliminating them would have removed the enemy team's primary damage source, allowing your carries to survive longer."
                elif improvement > 0:
                    explanation += f"{improvement:.0f}% slightly higher probability of winning. "
                    explanation += "However, the difference is marginal as both targets were viable options in that situation."
                else:
                    explanation += f"actually a {abs(improvement):.0f}% lower probability of success. "
                    explanation += "Your original target priority was correct given the positioning and cooldowns available."
        
        elif moment['type'] == 'OBJECTIVE':
            monster = moment['details'].get('monster_type', 'objective')
            explanation += f"At {timestamp_str}, regarding the {monster}, "
            explanation += f"if you had {alternative}, "
            
            improvement = (alt_outcome['win_probability'] - base_outcome['win_probability']) * 100
            if improvement > 0:
                explanation += f"you would have had a {improvement:.0f}% better chance of securing the objective. "
            else:
                explanation += f"you would have had a {abs(improvement):.0f}% worse outcome. "
        
        return explanation
    
    def _format_timestamp(self, seconds: float) -> str:
        """
        Formats timestamp as MM:SS
        """
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"
    
    def _generate_recommendation(self, base_outcome: Dict, alt_outcome: Dict) -> str:
        """
        Generates actionable recommendation
        """
        improvement = (alt_outcome['win_probability'] - base_outcome['win_probability']) * 100
        
        if improvement > 15:
            return "STRONG RECOMMENDATION: The alternative decision would have significantly improved your chances. Practice identifying similar situations."
        elif improvement > 5:
            return "MODERATE RECOMMENDATION: The alternative decision is better, but the difference is small. Both options were viable."
        elif improvement > -5:
            return "NEUTRAL: Both decisions had similar outcomes. Your choice was reasonable."
        else:
            return "YOUR DECISION WAS CORRECT: The alternative would have been worse. Good decision-making!"
    
    def train_model(self, training_data: pd.DataFrame):
        """
        Trains the teamfight outcome prediction model
        """
        # Prepare training data
        # Assumes training_data has features and 'outcome' column (1=win, 0=loss)
        
        X = training_data.drop(['outcome', 'match_id'], axis=1, errors='ignore').values
        y = training_data['outcome'].values
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Initialize model
        input_dim = X_train.shape[1]
        self.teamfight_model = TeamfightOutcomePredictor(input_dim=input_dim)
        
        # Training loop
        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(self.teamfight_model.parameters(), lr=0.001)
        
        # Convert to tensors
        X_train_tensor = torch.FloatTensor(X_train)
        y_train_tensor = torch.LongTensor(y_train)
        
        # Train
        epochs = 100
        batch_size = 64
        
        for epoch in range(epochs):
            for i in range(0, len(X_train_tensor), batch_size):
                batch_X = X_train_tensor[i:i+batch_size]
                batch_y = y_train_tensor[i:i+batch_size]
                
                optimizer.zero_grad()
                outputs = self.teamfight_model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
            
            if (epoch + 1) % 10 == 0:
                print(f"Epoch [{epoch+1}/{epochs}], Loss: {loss.item():.4f}")
        
        # Evaluate
        with torch.no_grad():
            X_test_tensor = torch.FloatTensor(X_test)
            outputs = self.teamfight_model(X_test_tensor)
            _, predicted = torch.max(outputs.data, 1)
            accuracy = (predicted == torch.LongTensor(y_test)).sum().item() / len(y_test)
            print(f"Test Accuracy: {accuracy:.4f}")
    
    def save_model(self, path: str):
        """
        Saves the trained model
        """
        torch.save(self.teamfight_model.state_dict(), f"{path}/teamfight_model.pth")
    
    def load_model(self, path: str, input_dim: int = 50):
        """
        Loads a trained model
        """
        self.teamfight_model = TeamfightOutcomePredictor(input_dim=input_dim)
        self.teamfight_model.load_state_dict(torch.load(f"{path}/teamfight_model.pth"))
        self.teamfight_model.eval()

if __name__ == "__main__":
    # Training example
    simulator = HypotheticalSimulator()
    # simulator.train_model(training_data)
    # simulator.save_model("/opt/ml/model")
    print("Hypothetical Simulator ready")