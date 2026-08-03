#pragma once
// Task_GunTrack -- gun-solution hold node (added 2026-08-01).
// Pure-pursuit aim (like Task_pure) but with a SPEED-MATCHING throttle instead of a fixed
// value, so once a firing solution is in hand the aircraft settles in the WEZ band and holds
// it rather than closing straight through it. Wired under Rule_forTraining.xml's Gate 2.5
// (GunSolutionHold), which only ticks this node when Distance is 150-914 m AND own ATA < 5 deg.
#include "../../behaviortree_cpp_v3\action_node.h"
#include "../../behaviortree_cpp_v3/bt_factory.h"
#include "../../../Geometry/Vector3.h"
#include "../Functions.h"
#include "../BlackBoard/CPPBlackBoard.h"

using namespace BT;

namespace Action
{
	class Task_GunTrack : public SyncActionNode
	{
	public:

		Task_GunTrack(const std::string& name, const NodeConfiguration& config) : SyncActionNode(name, config)
		{
		}

		~Task_GunTrack()
		{
		}

		static PortsList providedPorts();

		NodeStatus tick() override;
	};
}
