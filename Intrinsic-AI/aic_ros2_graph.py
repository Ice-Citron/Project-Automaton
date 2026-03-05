#!/usr/bin/env python3
"""
AIC (AI for Industry Challenge) — Complete ROS 2 Computation Graph
===================================================================
Generates a comprehensive visualization of all ROS 2 nodes, topics,
services, and actions in the AIC system.

Usage:
    python3 aic_ros2_graph.py

Output:
    aic_ros2_graph.png  (rendered image)
    aic_ros2_graph.pdf  (vector version)
    aic_ros2_graph.gv   (raw DOT source)
"""

import graphviz


def create_aic_graph():
    dot = graphviz.Digraph(
        "AIC_ROS2_Graph",
        comment="AI for Industry Challenge — ROS 2 Computation Graph",
        format="png",
    )

    # ── Global styling ──────────────────────────────────────────────
    dot.attr(
        rankdir="LR",
        bgcolor="#0d1117",
        fontname="Helvetica",
        fontsize="11",
        fontcolor="#c9d1d9",
        label=(
            "<<B><FONT POINT-SIZE='20' COLOR='#58a6ff'>"
            "AIC — ROS 2 Computation Graph</FONT></B>"
            "<BR/><FONT POINT-SIZE='12' COLOR='#8b949e'>"
            "AI for Industry Challenge  |  Cable Insertion Task  |  UR5e + Robotiq Hand-E"
            "</FONT>>"
        ),
        labelloc="t",
        pad="0.5",
        nodesep="0.4",
        ranksep="1.2",
        splines="true",
        overlap="false",
        concentrate="false",
    )

    # Edge defaults — use xlabel so labels always render
    dot.attr("edge", fontname="Courier", fontsize="8", fontcolor="#8b949e")

    # ── Style presets ───────────────────────────────────────────────
    NODE_PARTICIPANT = {
        "shape": "box", "style": "filled,bold", "fillcolor": "#1f6feb",
        "fontcolor": "white", "fontname": "Helvetica-Bold", "fontsize": "12",
        "penwidth": "2.5", "color": "#58a6ff",
    }
    NODE_EVAL = {
        "shape": "box", "style": "filled", "fillcolor": "#21262d",
        "fontcolor": "#c9d1d9", "fontname": "Helvetica-Bold", "fontsize": "12",
        "penwidth": "2", "color": "#30363d",
    }
    NODE_INFRA = {
        "shape": "box", "style": "filled,dashed", "fillcolor": "#161b22",
        "fontcolor": "#8b949e", "fontname": "Helvetica", "fontsize": "11",
        "penwidth": "1.5", "color": "#30363d",
    }
    NODE_SIM = {
        "shape": "box3d", "style": "filled", "fillcolor": "#0d4429",
        "fontcolor": "#3fb950", "fontname": "Helvetica-Bold", "fontsize": "12",
        "penwidth": "2", "color": "#238636",
    }

    TOPIC_SENSOR = {
        "shape": "ellipse", "style": "filled", "fillcolor": "#1a1e24",
        "fontcolor": "#f0883e", "fontname": "Courier", "fontsize": "9",
        "penwidth": "1", "color": "#d29922",
    }
    TOPIC_COMMAND = {
        "shape": "ellipse", "style": "filled", "fillcolor": "#1a1e24",
        "fontcolor": "#da3633", "fontname": "Courier", "fontsize": "9",
        "penwidth": "1", "color": "#f85149",
    }
    TOPIC_COMPOSITE = {
        "shape": "ellipse", "style": "filled,bold", "fillcolor": "#1a1e24",
        "fontcolor": "#a371f7", "fontname": "Courier Bold", "fontsize": "10",
        "penwidth": "1.5", "color": "#8957e5",
    }
    TOPIC_TF = {
        "shape": "ellipse", "style": "filled", "fillcolor": "#1a1e24",
        "fontcolor": "#79c0ff", "fontname": "Courier", "fontsize": "9",
        "penwidth": "1", "color": "#388bfd",
    }
    TOPIC_SCORING = {
        "shape": "ellipse", "style": "filled", "fillcolor": "#1a1e24",
        "fontcolor": "#3fb950", "fontname": "Courier", "fontsize": "9",
        "penwidth": "1", "color": "#238636",
    }

    SVC_STYLE = {
        "shape": "diamond", "style": "filled", "fillcolor": "#1a1e24",
        "fontcolor": "#d2a8ff", "fontname": "Courier", "fontsize": "8",
        "penwidth": "1", "color": "#8957e5",
    }
    ACTION_STYLE = {
        "shape": "hexagon", "style": "filled", "fillcolor": "#1a1e24",
        "fontcolor": "#ff7b72", "fontname": "Courier Bold", "fontsize": "9",
        "penwidth": "1.5", "color": "#f85149",
    }

    # Edge styles (all use xlabel instead of label)
    EDGE_DATA = {"color": "#f0883e", "penwidth": "1.2"}
    EDGE_CMD = {"color": "#f85149", "penwidth": "1.5", "style": "bold"}
    EDGE_TF = {"color": "#388bfd", "penwidth": "1", "style": "dashed"}
    EDGE_SCORE = {"color": "#238636", "penwidth": "1", "style": "dotted"}
    EDGE_SVC = {"color": "#8957e5", "penwidth": "1", "style": "dashed", "arrowhead": "odiamond"}
    EDGE_ACTION = {"color": "#f85149", "penwidth": "1.5", "style": "bold"}
    EDGE_BRIDGE = {"color": "#30363d", "penwidth": "1", "style": "dotted"}
    EDGE_COMPOSITE = {"color": "#8957e5", "penwidth": "1.5"}

    # ================================================================
    #  CLUSTER: SIMULATION (Gazebo)
    # ================================================================
    with dot.subgraph(name="cluster_sim") as sim:
        sim.attr(
            label="<<B>GAZEBO SIMULATION</B><BR/>"
                  "<FONT POINT-SIZE='9'>gz-sim  |  Bullet-Featherstone  |  2ms timestep</FONT>>",
            style="dashed", color="#238636", fontcolor="#3fb950",
            fontname="Helvetica", bgcolor="#0b1215",
        )
        sim.node("gz_server", "gz_server\n(Physics + Rendering)", **NODE_SIM)
        sim.node("gz_scoring_plugin", "ScoringPlugin\n(gz plugin)", **NODE_SIM)
        sim.node("gz_cable_plugin", "CablePlugin\n(gz plugin)", **NODE_SIM)
        sim.node("gz_offlimit_plugin", "OffLimitContacts\nPlugin (gz)", **NODE_SIM)

    # ================================================================
    #  CLUSTER: EVALUATION STACK
    # ================================================================
    with dot.subgraph(name="cluster_eval") as ev:
        ev.attr(
            label="<<B>EVALUATION STACK</B><BR/>"
                  "<FONT POINT-SIZE='9'>Organizer-provided  |  Read-only for participants</FONT>>",
            style="dashed", color="#30363d", fontcolor="#8b949e",
            fontname="Helvetica", bgcolor="#0d1117",
        )
        ev.node("aic_engine", "aic_engine\n(Trial Orchestrator)", **NODE_EVAL)
        ev.node("aic_controller", "aic_controller\n(ros2_control)\nCartesian + Joint\nImpedance Control", **NODE_EVAL)
        ev.node("aic_adapter", "aic_adapter\n(Sensor Fusion)\n@ 20 Hz", **NODE_EVAL)
        ev.node("aic_scoring", "aic_scoring\n(Tier 1/2/3)", **NODE_EVAL)
        ev.node("robot_state_pub", "robot_state\n_publisher", **NODE_INFRA)
        ev.node("joint_state_bc", "joint_state\n_broadcaster\n(ros2_control)", **NODE_INFRA)
        ev.node("fts_broadcaster", "fts_broadcaster\n(ros2_control)", **NODE_INFRA)
        ev.node("ros_gz_bridge", "ros_gz_bridge\n(GZ ↔ ROS)", **NODE_INFRA)

    # ================================================================
    #  CLUSTER: PARTICIPANT MODEL (your code!)
    # ================================================================
    with dot.subgraph(name="cluster_participant") as pt:
        pt.attr(
            label="<<B>YOUR SUBMISSION</B><BR/>"
                  "<FONT POINT-SIZE='9'>aic_model container  |  "
                  "Implement Policy.insert_cable()</FONT>>",
            style="bold", color="#1f6feb", fontcolor="#58a6ff",
            fontname="Helvetica-Bold", bgcolor="#0d1420",
        )
        pt.node("aic_model", "aic_model\n(LifecycleNode)\n+ YourPolicy", **NODE_PARTICIPANT)

    # ================================================================
    #  TOPICS
    # ================================================================
    # Sensor data (orange)
    for cam in ["left", "center", "right"]:
        dot.node(f"t_{cam}_image", f"/{cam}_camera/image\nImage", **TOPIC_SENSOR)
        dot.node(f"t_{cam}_info", f"/{cam}_camera/\ncamera_info\nCameraInfo", **TOPIC_SENSOR)

    dot.node("t_joint_states", "/joint_states\nJointState [7]", **TOPIC_SENSOR)
    dot.node("t_fts_wrench", "/fts_broadcaster\n/wrench\nWrenchStamped", **TOPIC_SENSOR)
    dot.node("t_controller_state", "/aic_controller\n/controller_state\nControllerState", **TOPIC_SENSOR)
    dot.node("t_clock", "/clock\nClock (sim time)", **TOPIC_SENSOR)

    # Composite observation (purple)
    dot.node(
        "t_observations",
        "/observations\nObservation @ 20Hz\n"
        "3 images + joints\n"
        "+ wrench + ctrl_state",
        **TOPIC_COMPOSITE,
    )

    # Commands (red)
    dot.node("t_pose_cmds", "/aic_controller\n/pose_commands\nMotionUpdate", **TOPIC_COMMAND)
    dot.node("t_joint_cmds", "/aic_controller\n/joint_commands\nJointMotionUpdate", **TOPIC_COMMAND)

    # TF (blue)
    dot.node("t_tf", "/tf\nTFMessage\n(robot kinematic\nframes)", **TOPIC_TF)
    dot.node("t_tf_static", "/tf_static\nTFMessage\n(static frames)", **TOPIC_TF)
    dot.node("t_scoring_tf", "/scoring/tf\nTFMessage\n(cable + task_board\nground truth)", **TOPIC_TF)

    # Scoring (green)
    dot.node("t_off_limit", "/aic/gazebo/contacts\n/off_limit\nContacts", **TOPIC_SCORING)
    dot.node("t_insertion", "/scoring/\ninsertion_event\nString", **TOPIC_SCORING)

    # Services (purple diamonds)
    dot.node("s_change_mode", "/aic_controller/\nchange_target_mode\nChangeTargetMode.srv", **SVC_STYLE)
    dot.node("s_cancel_task", "/cancel_task\nEmpty.srv", **SVC_STYLE)
    dot.node("s_reset_joints", "/reset_joints\nResetJoints.srv", **SVC_STYLE)

    # Actions (red hexagons)
    dot.node(
        "a_insert_cable",
        "/insert_cable\nInsertCable.action\nGoal(Task) →\nResult(bool)\n+ Feedback(str)",
        **ACTION_STYLE,
    )

    # ================================================================
    #  EDGES: Gazebo → ROS bridge → topics
    # ================================================================
    for cam in ["left", "center", "right"]:
        dot.edge("gz_server", "ros_gz_bridge", **EDGE_BRIDGE)
    # (single bridge edge is cleaner — the bridge fans out)
    for cam in ["left", "center", "right"]:
        dot.edge("ros_gz_bridge", f"t_{cam}_image", **EDGE_BRIDGE)
        dot.edge("ros_gz_bridge", f"t_{cam}_info", **EDGE_BRIDGE)

    dot.edge("ros_gz_bridge", "t_clock", xlabel="sim clock", **EDGE_BRIDGE)
    dot.edge("gz_offlimit_plugin", "ros_gz_bridge", **EDGE_BRIDGE)
    dot.edge("ros_gz_bridge", "t_off_limit", **EDGE_BRIDGE)
    dot.edge("gz_scoring_plugin", "ros_gz_bridge", **EDGE_BRIDGE)
    dot.edge("ros_gz_bridge", "t_scoring_tf", xlabel="cable/board poses", **EDGE_BRIDGE)
    dot.edge("gz_cable_plugin", "ros_gz_bridge", **EDGE_BRIDGE)
    dot.edge("ros_gz_bridge", "t_insertion", **EDGE_BRIDGE)

    # ================================================================
    #  EDGES: ros2_control broadcasters
    # ================================================================
    dot.edge("joint_state_bc", "t_joint_states", **EDGE_DATA)
    dot.edge("fts_broadcaster", "t_fts_wrench", **EDGE_DATA)

    # ================================================================
    #  EDGES: robot_state_publisher
    # ================================================================
    dot.edge("robot_state_pub", "t_tf", xlabel="URDF FK", **EDGE_TF)
    dot.edge("robot_state_pub", "t_tf_static", **EDGE_TF)
    dot.edge("t_joint_states", "robot_state_pub", **EDGE_DATA)

    # ================================================================
    #  EDGES: aic_controller
    # ================================================================
    dot.edge("t_pose_cmds", "aic_controller", xlabel="Cartesian impedance", **EDGE_CMD)
    dot.edge("t_joint_cmds", "aic_controller", xlabel="Joint impedance", **EDGE_CMD)
    dot.edge("aic_controller", "t_controller_state", **EDGE_DATA)
    dot.edge("s_change_mode", "aic_controller", **EDGE_SVC)

    # ================================================================
    #  EDGES: aic_adapter (sensor fusion → composite observation)
    # ================================================================
    for cam in ["left", "center", "right"]:
        dot.edge(f"t_{cam}_image", "aic_adapter", **EDGE_DATA)
        dot.edge(f"t_{cam}_info", "aic_adapter", **EDGE_DATA)

    dot.edge("t_joint_states", "aic_adapter", **EDGE_DATA)
    dot.edge("t_fts_wrench", "aic_adapter", **EDGE_DATA)
    dot.edge("t_controller_state", "aic_adapter", **EDGE_DATA)
    dot.edge("aic_adapter", "t_observations", xlabel="time-synced composite", **EDGE_COMPOSITE)

    # ================================================================
    #  EDGES: aic_model (YOUR CODE — the critical data flow)
    # ================================================================
    dot.edge("t_observations", "aic_model", xlabel="get_observation()", **EDGE_COMPOSITE)
    dot.edge("aic_model", "t_pose_cmds",
             xlabel="move_robot(motion_update=...)", **EDGE_CMD)
    dot.edge("aic_model", "t_joint_cmds",
             xlabel="move_robot(joint_motion_update=...)", **EDGE_CMD)
    dot.edge("aic_model", "s_change_mode", xlabel="auto switch", **EDGE_SVC)
    dot.edge("t_tf", "aic_model",
             xlabel="TF buffer (training only)",
             **EDGE_TF)
    dot.edge("t_scoring_tf", "aic_model",
             xlabel="FORBIDDEN in eval!",
             style="dotted", color="#f85149",
             fontcolor="#f85149", fontname="Courier", fontsize="8", penwidth="1")

    # ================================================================
    #  EDGES: aic_engine (orchestrator)
    # ================================================================
    dot.edge("aic_engine", "a_insert_cable", xlabel="sends goal", **EDGE_ACTION)
    dot.edge("a_insert_cable", "aic_model", xlabel="triggers insert_cable()", **EDGE_ACTION)
    dot.edge("t_joint_cmds", "aic_engine", xlabel="monitors cmds", **EDGE_SCORE)
    dot.edge("t_pose_cmds", "aic_engine", xlabel="monitors cmds", **EDGE_SCORE)
    dot.edge("t_joint_states", "aic_engine", **EDGE_SCORE)

    # ================================================================
    #  EDGES: aic_scoring
    # ================================================================
    dot.edge("t_scoring_tf", "aic_scoring", xlabel="plug/port positions", **EDGE_SCORE)
    dot.edge("t_off_limit", "aic_scoring", xlabel="contact violations", **EDGE_SCORE)
    dot.edge("t_fts_wrench", "aic_scoring", xlabel="force magnitude", **EDGE_SCORE)
    dot.edge("t_joint_states", "aic_scoring", **EDGE_SCORE)
    dot.edge("t_tf", "aic_scoring", **EDGE_SCORE)
    dot.edge("t_insertion", "aic_scoring", xlabel="insertion events", **EDGE_SCORE)
    dot.edge("t_controller_state", "aic_scoring", **EDGE_SCORE)

    # ================================================================
    #  EDGES: Services
    # ================================================================
    dot.edge("aic_engine", "s_cancel_task", **EDGE_SVC)
    dot.edge("s_cancel_task", "aic_model", **EDGE_SVC)
    dot.edge("s_reset_joints", "gz_server", **EDGE_SVC)

    # ================================================================
    #  LEGEND
    # ================================================================
    with dot.subgraph(name="cluster_legend") as lg:
        lg.attr(
            label="<<B>LEGEND</B>>",
            style="rounded", color="#30363d", fontcolor="#8b949e",
            fontname="Helvetica", bgcolor="#0d1117", rank="sink",
        )
        lg.node("leg_participant", "  Your Code  ", shape="box", style="filled,bold",
                fillcolor="#1f6feb", fontcolor="white", fontname="Helvetica-Bold",
                fontsize="10", penwidth="2", color="#58a6ff")
        lg.node("leg_eval", "  Eval Stack  ", shape="box", style="filled",
                fillcolor="#21262d", fontcolor="#c9d1d9", fontname="Helvetica-Bold",
                fontsize="10", penwidth="2", color="#30363d")
        lg.node("leg_sim", "  Simulation  ", shape="box3d", style="filled",
                fillcolor="#0d4429", fontcolor="#3fb950", fontname="Helvetica-Bold",
                fontsize="10", penwidth="2", color="#238636")
        lg.node("leg_topic_sensor", "  /sensor_topic  ", shape="ellipse", style="filled",
                fillcolor="#1a1e24", fontcolor="#f0883e", fontname="Courier",
                fontsize="9", color="#d29922")
        lg.node("leg_topic_cmd", "  /command_topic  ", shape="ellipse", style="filled",
                fillcolor="#1a1e24", fontcolor="#da3633", fontname="Courier",
                fontsize="9", color="#f85149")
        lg.node("leg_topic_comp", "  /composite  ", shape="ellipse", style="filled,bold",
                fillcolor="#1a1e24", fontcolor="#a371f7", fontname="Courier",
                fontsize="9", penwidth="1.5", color="#8957e5")
        lg.node("leg_topic_tf", "  /tf_topic  ", shape="ellipse", style="filled",
                fillcolor="#1a1e24", fontcolor="#79c0ff", fontname="Courier",
                fontsize="9", color="#388bfd")
        lg.node("leg_svc", "  /service  ", shape="diamond", style="filled",
                fillcolor="#1a1e24", fontcolor="#d2a8ff", fontname="Courier",
                fontsize="9", color="#8957e5")
        lg.node("leg_action", "  /action  ", shape="hexagon", style="filled",
                fillcolor="#1a1e24", fontcolor="#ff7b72", fontname="Courier",
                fontsize="9", color="#f85149")

        lg.edge("leg_participant", "leg_eval", style="invis")
        lg.edge("leg_eval", "leg_sim", style="invis")
        lg.edge("leg_sim", "leg_topic_sensor", style="invis")
        lg.edge("leg_topic_sensor", "leg_topic_cmd", style="invis")
        lg.edge("leg_topic_cmd", "leg_topic_comp", style="invis")
        lg.edge("leg_topic_comp", "leg_topic_tf", style="invis")
        lg.edge("leg_topic_tf", "leg_svc", style="invis")
        lg.edge("leg_svc", "leg_action", style="invis")

    return dot


if __name__ == "__main__":
    import os
    import subprocess
    import sys

    script_dir = os.path.dirname(os.path.abspath(__file__))
    dot = create_aic_graph()

    dot_path = os.path.join(script_dir, "aic_ros2_graph")
    dot.render(dot_path, format="png", cleanup=False)
    dot.render(dot_path, format="pdf", cleanup=False)

    print(f"Generated:")
    print(f"  {dot_path}.gv   (DOT source — editable)")
    print(f"  {dot_path}.png  (raster image)")
    print(f"  {dot_path}.pdf  (vector — zoom infinitely)")
    print()

    # Auto-open on macOS
    png_path = f"{dot_path}.png"
    if sys.platform == "darwin" and os.path.exists(png_path):
        subprocess.run(["open", png_path])
        print("Opened PNG in Preview.")
