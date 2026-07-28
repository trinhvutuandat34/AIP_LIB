# 2026 AI Pilot Top Gun Challenge

## 📋 Overview
**Tagline:** AI Takes Flight
**Competition Technology Partner:** REALTIMEVISUAL

### Key Statistics
- **Total Participating Teams:** 288
- **Sponsors:** 11 major organizations including KASA, Korean Air, LIG Defense & Aerospace, Hyundai Rotem, and others

---

## 🎯 Competition Structure

### Prize Distribution (상금 체계)
| Rank | Sponsoring Organization | Prize (₩) | Notes |
|------|------------------------|-----------|-------|
| **Grand Prize** | Science & Technology Information Ministry + Korean Aerospace University | 1,000 | Winning Team |
| **2nd Place** | Public Procurement Service | 500 | Runner-up Team |
| **3rd Place** | Ministry of Defense + Space Agency | 200 | 3-4 Teams |
| **Academic Award** | Korean Air | 200 | Best Academic Presentation |
| **Excellence Award** | KAI, Hanwha Systems, Hyundai Rotem, LIG D&A | 100 | 8 Teams |
| **Encouragement Award** | Korean Aerospace University SW Research Center | 50 | Finalist Teams |

---

## 🌐 Background Context

### International Competition Reference
- **Title:** "AI Pilot vs Human Pilot... F-16 Fighter Actual 'Dogfight' Test"
- **Source:** Media coverage from September 2024 (US Military magazine)
- **Context:** Discussion about AI pilots in real combat scenarios, with references to defense policy implications

### Domestic Military AI Development
- **ADD (Agency for Defense Development):** Developing "AI Pilot" for autonomous fighter aircraft
- **Focus:** Creating AI combat decision-making systems and comprehensive training frameworks
- **Timeline:** Development phase with public demonstration and technology transfer initiatives
- **Key Takeaway:** First evaluation by military experts showing 90% combat success rate in initial testing

---

## 🚀 Challenge Objectives

### What Makes This Competition Unique
Each participating team will develop AI fighter aircraft agents leveraging REALTIMEVISUAL-provided development environments to:
1. Create knowledge & rule-based AI pilots
2. Train AI pilots that can make superior strategic decisions
3. Build AI models capable of realistic dogfighting behavior
4. Achieve the highest combat success rates in autonomous scenarios

### Key Development Environment Requirements
- **Provided by:** REALTIMEVISUAL (technology partner)
- **Certainty Level:** Definite and controlled simulation conditions
- **Delivery:** Provided as reliable infrastructure throughout competition

---

## 📊 Challenge Scenarios

### Teaching Scenarios (교전 롤 : 교전 대미지 롤)

#### Engagement Range Phases
The teaching scenarios follow a phased damage model system with three distinct operational phases:

**Phase 1 (LOS < 1°, 500ft < Distance < 3000ft, Damage Factor = 1)**
- Close visual range engagement
- High probability of successful targeting
- Tactical maneuvering critical

**Phase 2 (LOS < 2°, 500ft < Distance < 3500ft, Damage Factor = 0.3)**
- Medium-range engagement window
- Reduced lethality but still effective
- Decision-making becomes more complex

**Phase 3 (LOS < 3°, 500ft < Distance < 4000ft, Damage Factor = 0.1)**
- Extended range engagement zone
- Significant challenge dynamics
- Strategic positioning essential

#### Damage Cone Visualization
- Enemy aircraft centered at origin (LOS 0°)
- 3-phase cone system showing damage probability
- Distance-based modulation of engagement effectiveness
- Progressive increase in tactical complexity

#### Damage Calculation Formula

```
Dwex = { 
  0                           (r > 3000 ft)
  1.0 × (3000-r)/2500        (500 ft < r ≤ 3000 ft, |θ| < 1°)
  0.3 × (3500-r)/3000        (500 ft < r ≤ 3500 ft, |θ| < 2°)
  0.1 × (4000-r)/3500        (500 ft < r ≤ 4000 ft, |θ| < 3°)
  0                           (r < 500 ft)
}
```

---

## 🎮 Competition Rules

### Base (Base) Scenario
- **Rounds:** 1-3
- **Distance:** 2000ft - 3000ft
- **AI Training Method:** AlphaDogFight competition methodology

### Final (Final) Scenario
- **Rounds:** 1-3 Qualifiers
- **Condition:** When teams advance beyond base qualification
- **Execution:** Standard AlphaDogFight teaching methodology applied

### Advanced Scenario (Advanced+)
- **Distance:** 10,000ft or greater
- **Complexity:** Significantly increased engagement dynamics
- **Challenge Level:** Teams advancing beyond round 3 face evolved strategic requirements
- **Goal:** Achieve maximum combat effectiveness at extreme ranges

---

## 🛠️ Development Environment Setup

### Overview
Each participating team receives from REALTIMEVISUAL:
1. **AI Fighter Development Environment** through AlphaDogFight framework
2. **Integrated Training & Testing Infrastructure**
3. **Behavior Tree-based decision-making system**
4. **Physical simulation environment** (JSBSIM controller)

### Technical Specifications

#### Observation Engineering
- **Perfect State Information (Ground-truth state information)**
  - Aircraft location, attitude, and velocity
  - Enemy aircraft position and velocity
  - Engagement parameters provided at 60Hz frame rate
  - Real-time state updates at 0.01666s intervals

#### Network Architecture
- Accepts state information from observation layer
- Processes enemy aircraft position and velocity data
- Outputs command structure: Roll, Pitch, Yaw, Throttle
- Integrated with JSBSIM physics simulator for realistic dynamics

#### Training Approach
- **Constraint-based learning** (leveraging aircraft dynamics)
- **Simplified curriculum** for progressive skill development
- **Behavior Tree validation** within learning environment
- **AI trainer server** for continuous feedback and adaptation

---

## 🧠 AI Development Strategy

### Core Components

#### 1. **Rule-Based AI (기존 기반 모델)**
- **Advantages:**
  - Deterministic decision-making
  - Explicit control over behavior
  - Development transparency
- **Disadvantages:**
  - Limited adaptability
  - Complex rule engineering required
  - Scalability challenges

#### 2. **Supervised Learning AI**
- **Advantages:**
  - Good training data yields reliable behavior
  - Interpretable decision-making
- **Disadvantages:**
  - Requires extensive labeled datasets
  - Difficult to generalize beyond training scenarios

#### 3. **Reinforcement Learning AI (강화학습 기반)**
- **Advantages:**
  - High engagement success rates
  - Domain expertise learning capability
  - Self-improvement through interaction
- **Disadvantages:**
  - Requires significant training time
  - Hyperparameter tuning complexity
  - Safety considerations during development

#### 4. **Hybrid Approach (Advanced Hybrid)**
- Combines multiple AI methodologies
- Leverages Rule-based systems for core operations
- Applies reinforcement learning for tactical optimization
- Demonstrates superior performance in benchmark scenarios

---

## 📐 Fighter Aircraft Model Representation

### Pilot Input Structure
- **Stick Input (Roll & Pitch):** Rudder (Yaw)
- **Throttle Command:** Engine thrust management

### Pilot Decision Process
- Receives target position and velocity information
- Processes enemy aircraft state through neural/rule network
- Outputs coordinated aircraft control commands (CMD: Roll, Pitch, Yaw, Throttle)
- Maintains real-time synchronization with physics engine

### Fight Dynamics Model
- **Natural Frequency (Natural oscillation characteristics):** Determined by aircraft type
- **Damping Ratio:** Progressive attenuation of maneuvers
- **Control Response:** Realistic lag and acceleration limits

---

## 🎓 Behavior Tree-Based AI Development

### Behavior Tree Fundamentals
Behavior Trees are hierarchical decision-making structures that:
- Represent complex AI behavior through modular node composition
- Enable clear logic flow with systematic evaluation
- Support both knowledge-based and learned components
- Facilitate team collaboration on AI development

### Core Node Types

**Flow Control Nodes**
- **Sequence:** Execute child nodes sequentially; if any fail, abort
- **Selector:** Try child nodes; stop at first success
- **Fallback:** Similar to selector; attempt alternatives until success

**Content Nodes**
- **Task Nodes:** Execute specific combat actions (VP generation, targeting)
- **Decorator Nodes:** Modify execution conditions; gate behaviors with if/conditions
- **Service Nodes:** Update persistent state; maintain game environment knowledge

### Development Workflow

```
Behavior Tree Development 
  ↓
Rule-based/Logical Model with DLL & XML
  ↓
Reinforcement Learning AI Model
  ↓
Model Integration in Hybrid Architecture
  ↓
Unified AI Decision-Making System
```

### Key Concept
Combine logical decision frameworks with learned tactical models to create robust AI pilots that can adapt to novel scenarios while maintaining predictable, understandable behavior.

---

## 🔧 Implementation Details

### Behavior Tree Architecture Components
1. **Tree Structure (XML format)**
   - Defines hierarchical node relationships
   - Specifies node types and parameters
2. **BlackBoard (Knowledge Management)**
   - Centralized state storage accessible to all nodes
   - Maintains aircraft state, distance, LOS information
3. **Selector/Sequence Logic**
   - **Selector:** Returns success if any child succeeds
   - **Sequence:** Returns success only if all children succeed
4. **Decorator Nodes**
   - Check conditions before task execution
   - If/else branches based on blackboard data
5. **Service Nodes**
   - State update mechanisms
   - Enable dynamic knowledge refresh

### Fighter Dynamics Integration
**JSBSIM Controller Role**
- Converts tree-based commands to realistic aircraft dynamics
- Receives Roll, Pitch, Yaw, Throttle outputs
- Simulates 6-DOF aircraft motion
- Returns updated state to observation layer

### Teaching Environment (교전 시나리오 룰)
The learning environment provides structured progression:

#### Qualifiers (1-3 Rounds)
- Basic engagement scenarios
- 2000-3000ft range
- AlphaDogFight teaching methodology
- Foundation skill development

#### Advanced Rounds (4+ Rounds)
- Extended range scenarios (10,000ft+)
- Increased complexity
- Advanced tactical requirements
- Teams demonstrate mastery through progressive challenges

---

## 🚀 Getting Started

### Development Environment Setup
1. **Install Anaconda & Python 3.11**
   - Create virtual environment: `conda create -n aip python=3.11`
   
2. **Configure Workspace**
   - Navigate to project root: `C:\Users\[username]\Desktop\AIP\DogFightEnv\Release`
   
3. **Install Dependencies**
   - Run: `python -m pip install -r requirements.txt`
   
4. **Verify Setup**
   - Test: `python -c "import JSBSimWrapper; print('ok')"`

### Build & Deployment
1. **Build XML Behavior Tree**
   - Place `Rule_forTraining.xml` in project directory
   
2. **Compile DLL & XML**
   - Output: `AIP_DCS.dll` in `/bin/debug.x64` folder
   
3. **Execute Test**
   - Run: `python run_unreal_inference.py --mode bt --team-name TestLaptop --server-ip 123.456.789.529 --server-port 9999`
   
4. **Verify Connection**
   - Confirm team connection to OpenServer
   - Begin competitive testing

### Behavior Tree Tutorial
The competition provides comprehensive tutorials on:
- **Unreal Engine Behavior Tree structure**
- **C++ Behavior Tree node creation**
- **Custom action node implementation**
- **XML-based tree configuration**
- **Integration with JSBSIM physics engine**

---

## 📚 Additional Resources

### Key Concepts
- **AlphaDogFight:** DARPA's autonomous air combat framework
- **SAC (Soft Actor-Critic):** Reinforcement learning algorithm for continuous control
- **Behavior Trees:** Hierarchical state machine alternative for behavior modeling
- **JSBSIM:** Open-source flight dynamics model

### References
- BehaviorTree.CPP 4.6 Library: https://www.behaviortree.dev/
- Competition Discord: https://discord.gg/RagK27Av
- **Note:** Discord server valid for 7 days from challenge start

---

## 🏆 Competition Timeline
- **August:** Preliminary qualification rounds (1-3 rounds)
- **September:** Select 8 teams + 4 runners-up to advance
- **September (mid):** Tournament begins; 1 team selected as champion
- **Final Selection:** Winning team announced through tournament bracket

---

## ⚠️ Important Notes

### Development Requirements
- Minimum 2 team members recommended (1 server + 1 access point)
- Sufficient network connectivity for remote testing
- Understanding of fighter aircraft dynamics beneficial but not required
- Familiarity with behavior trees and/or reinforcement learning

### Support & Community
- Official Discord server for team communication and technical support
- Regular competition updates and clarifications
- Access to baseline code and documentation
- Mentor support for technical challenges

---
*Last Updated: 2026 AI Pilot Top Gun Challenge Official Documentation*
