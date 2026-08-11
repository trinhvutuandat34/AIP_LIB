// GateTrace.h -- which BT branch actually wins, per tick, from inside the tree.
//
// WHY THIS EXISTS. COMPETITION_PLAN.md 4.1 F20: four rounds of trying to identify the winning
// gate at the official beam merge by perturbing the rule XML and reading episode outcomes
// produced three wrong conclusions (F16 a false null, F18 blaming the peer rig, F19 blaming the
// recycler). Outcome-level inference cannot resolve gate selection here -- the tree edits were
// bit-identical in 29/30 episodes, which says "no decision changed" but not WHICH decision was
// being made. This reports the decision directly.
//
// It also settles F17's one untested premise. F17 argued Task_Notch shadows the whole Gate 2
// block at the merge because its conditions (Distance <= 2000 m, target ATA 70-110 deg) are
// satisfied by the 610-914 m / ~90 deg spawn. But Task_Notch ALSO requires EnemyInSight_Target,
// which nothing has ever checked. If that is false at the spawn, Gate 1 never fires and F17 is
// wrong. The EnemyInSight_Target column answers it on the first logged row.
//
// HOW. BT::Tree exposes `nodes`, and every TreeNode has name() and status(). After tickRoot()
// the winning path is exactly the set of nodes left in SUCCESS or RUNNING, so no per-node
// instrumentation is needed and no BehaviorTree.CPP internals are modified. (The library's
// StatusChangeLogger would have been the idiomatic route, but only its HEADER is vendored here --
// there is no abstract_logger.cpp on disk, so subclassing it would not link.)
//
// COST WHEN DISABLED: one test of a cached static bool per tick. The env var is read once.
// Leave AIP_BT_GATE_TRACE unset and this is inert, so it is safe to leave in the submission DLL.
//
// USAGE
//     set AIP_BT_GATE_TRACE=D:\path\gate_trace.csv     (unset = off)
//     set AIP_BT_GATE_TRACE_FIRST=300                  (optional; default 300 ticks = 5 s @60Hz)
//
// Rows are written for the first AIP_BT_GATE_TRACE_FIRST ticks of each tree -- which covers the
// merge, the phase in question -- and thereafter ONLY when the winning path changes. That keeps a
// 30-episode run to a readable file instead of ~720k rows.
//
// Both aircraft write to the same file; the `id` column separates them. Writes are mutex-guarded
// because the two trees tick from the same sim thread but nothing here should assume that.
//
// REVERT: delete this file and the two lines in CPPBehaviorTree.cpp that include and call it.

#pragma once

#include <cstdlib>
#include <fstream>
#include <mutex>
#include <string>
#include <vector>

#include "./behaviortree_cpp_v3/bt_factory.h"
#include "./BlackBoard/CPPBlackBoard.h"

namespace GateTrace
{
	inline bool ReadEnv(const char* name, std::string& out)
	{
#ifdef _MSC_VER
		char* buf = nullptr;
		size_t len = 0;
		if (_dupenv_s(&buf, &len, name) != 0 || buf == nullptr)
			return false;
		out.assign(buf);
		free(buf);
		return !out.empty();
#else
		const char* v = std::getenv(name);
		if (v == nullptr || *v == '\0')
			return false;
		out.assign(v);
		return true;
#endif
	}

	// Read once. Empty path => tracing off for the life of the process.
	inline const std::string& TracePath()
	{
		static const std::string path = []() {
			std::string p;
			return ReadEnv("AIP_BT_GATE_TRACE", p) ? p : std::string();
		}();
		return path;
	}

	inline bool Enabled()
	{
		static const bool on = !TracePath().empty();
		return on;
	}

	inline int FirstTicks()
	{
		static const int n = []() {
			std::string v;
			if (!ReadEnv("AIP_BT_GATE_TRACE_FIRST", v))
				return 300;
			try { return std::stoi(v); } catch (...) { return 300; }
		}();
		return n;
	}

	// Include FAILURE transitions. Off by default: every rejected gate would be logged each tick.
	inline bool TraceAll()
	{
		static const bool all = []() {
			std::string v;
			return ReadEnv("AIP_BT_GATE_TRACE_ALL", v) && v != "0";
		}();
		return all;
	}

	inline std::mutex& Lock()
	{
		static std::mutex m;
		return m;
	}

	// Per-tree state, owned by the caller so two aircraft cannot share it.
	//
	// `subs` MUST outlive the tree: subscribeToStatusChange returns a shared_ptr handle and the
	// callback is unsubscribed the moment it drops, so holding the handles here is what keeps the
	// tracing alive. `pending` accumulates transitions DURING a tick.
	struct State
	{
		long long ticks = 0;
		std::string last_path;
		std::vector<BT::TreeNode::StatusChangeSubscriber> subs;
		std::string pending;
		bool attached = false;
	};

	inline const char* StatusName(BT::NodeStatus s)
	{
		switch (s)
		{
		case BT::NodeStatus::SUCCESS: return "S";
		case BT::NodeStatus::RUNNING: return "R";
		case BT::NodeStatus::FAILURE: return "F";
		default:                      return "I";
		}
	}

	// Subscribe to every node's status change ONCE, so transitions are captured DURING the tick.
	//
	// The obvious approach -- read node->status() after tickRoot() -- does NOT work and silently
	// yields an empty path: BehaviorTree.CPP resets nodes to IDLE when a tick completes, so by
	// the time control returns, nothing is left in SUCCESS or RUNNING. Measured: 201 trace rows,
	// every winning_path blank. Subscribing is what StatusChangeLogger does internally, and
	// tree_node.cpp (which IS compiled here) implements it.
	inline void Attach(State& st, BT::Tree& tree)
	{
		if (st.attached)
			return;
		st.attached = true;

		// One-time inventory of what the factory actually BUILT. Written because the trace showed
		// a Sequence succeeding with no children ticking, and an empty Sequence returns SUCCESS
		// immediately in BehaviorTree.CPP -- so the question is whether those children exist in
		// the tree at all, or were silently dropped at parse time.
		if (Enabled())
		{
			std::lock_guard<std::mutex> guard(Lock());
			std::ofstream inv(TracePath() + ".nodes.txt", std::ios::app);
			if (inv)
			{
				inv << "--- tree node inventory (" << tree.nodes.size() << " nodes) ---\n";
				for (const auto& n : tree.nodes)
					if (n)
						inv << "  " << n->registrationName() << "  name=\"" << n->name()
						    << "\"  children="
						    << (n->type() == BT::NodeType::ACTION ? 0 : -1) << "\n";
			}
		}

		for (const auto& node : tree.nodes)
		{
			if (!node || node->name().empty())
				continue;
			BT::TreeNode* raw = node.get();
			st.subs.push_back(raw->subscribeToStatusChange(
				[&st, raw](BT::TimePoint, const BT::TreeNode&, BT::NodeStatus, BT::NodeStatus status)
				{
					// By default only the branch that ran is interesting; FAILURE is every gate
					// tested and rejected, which swamps the file. Set AIP_BT_GATE_TRACE_ALL=1 to
					// include FAILURE -- needed when a gate succeeds whose conditions appear
					// unsatisfiable, because then the rejected children are the evidence.
					if (!TraceAll() && status != BT::NodeStatus::SUCCESS
					    && status != BT::NodeStatus::RUNNING)
						return;
					if (status == BT::NodeStatus::IDLE)
						return;
					if (!st.pending.empty())
						st.pending += "|";
					st.pending += raw->name();
					st.pending += ":";
					st.pending += StatusName(status);
				}));
		}
	}

	// Call immediately after tree.tickRoot(). Inert unless AIP_BT_GATE_TRACE is set.
	inline void Record(State& st, BT::Tree& tree, const CPPBlackBoard* BB, int id, int force_id)
	{
		if (!Enabled() || BB == nullptr)
			return;

		// Transitions were collected by the subscribers during the tick just completed.
		const std::string path = st.pending;
		st.pending.clear();
		const bool early = (st.ticks < FirstTicks());
		const bool changed = (path != st.last_path);
		st.ticks++;
		if (!early && !changed)
			return;
		st.last_path = path;

		std::lock_guard<std::mutex> guard(Lock());
		static bool header_written = false;
		std::ofstream f(TracePath(), std::ios::app);
		if (!f)
			return;
		if (!header_written)
		{
			f << "id,force_id,tick,running_time,distance_m,los_own_deg,los_target_deg,"
			     "hca_deg,aspect_deg,enemy_in_sight,enemy_in_sight_target,alt_speed_mps,"
			     "energy_ratio,active_maneuver,winning_path\n";
			header_written = true;
		}
		f << id << ',' << force_id << ',' << (st.ticks - 1) << ','
		  << BB->RunningTime << ','
		  << BB->Distance << ','
		  << BB->Los_Degree << ','
		  << BB->Los_Degree_Target << ','
		  << BB->MyAngleOff_Degree << ','
		  << BB->MyAspectAngle_Degree << ','
		  << (BB->EnemyInSight ? 1 : 0) << ','
		  << (BB->EnemyInSight_Target ? 1 : 0) << ','
		  << BB->AltSpeed << ','
		  << BB->EnergyRatio << ','
		  << static_cast<int>(BB->ActiveManeuverID) << ','
		  << path << '\n';
	}
}
