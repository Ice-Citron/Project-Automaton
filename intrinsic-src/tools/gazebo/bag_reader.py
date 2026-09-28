#!/usr/bin/env python3
"""
AIC Bag File Reader — Extract and visualize data from AIC trial recordings.

Usage (from the aic workspace):
  cd ~/projects/Project-Automaton/References/aic
  pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/bag_reader.py <bag_dir> [--plot]

Examples:
  # Print summary of a trial bag
  pixi run python3 ../Intrinsic-AI/bag_reader.py ~/projects/Project-Automaton/aic_results/bag_trial_1_20260320_185331_556

  # Plot joint positions and forces over time
  pixi run python3 ../Intrinsic-AI/bag_reader.py ~/projects/Project-Automaton/aic_results/bag_trial_1_20260320_185331_556 --plot
"""

import argparse
import json
import os
import struct
import sys
from pathlib import Path

from mcap.reader import make_reader


def find_mcap_file(bag_dir: str) -> str:
    """Find the .mcap file inside a bag directory."""
    bag_path = Path(bag_dir)
    mcap_files = list(bag_path.glob("*.mcap"))
    if not mcap_files:
        print(f"No .mcap files found in {bag_dir}")
        sys.exit(1)
    return str(mcap_files[0])


def print_summary(mcap_path: str):
    """Print a human-readable summary of the bag file."""
    with open(mcap_path, "rb") as f:
        reader = make_reader(f)
        summary = reader.get_summary()
        stats = summary.statistics

        duration_s = (stats.message_end_time - stats.message_start_time) / 1e9
        print(f"{'='*60}")
        print(f"BAG FILE SUMMARY")
        print(f"{'='*60}")
        print(f"File: {mcap_path}")
        print(f"Duration: {duration_s:.1f} seconds")
        print(f"Total messages: {stats.message_count}")
        print(f"")
        print(f"{'Topic':<45} {'Type':<40} {'Count':>8}")
        print(f"{'-'*45} {'-'*40} {'-'*8}")

        for ch_id, ch in sorted(summary.channels.items(), key=lambda x: x[1].topic):
            schema = summary.schemas.get(ch.schema_id)
            schema_name = schema.name if schema else "unknown"
            count = stats.channel_message_counts.get(ch_id, 0)
            print(f"{ch.topic:<45} {schema_name:<40} {count:>8}")


def extract_joint_states(mcap_path: str):
    """Extract joint positions over time from /joint_states topic."""
    import struct

    timestamps = []
    positions_list = []
    joint_names = None

    with open(mcap_path, "rb") as f:
        reader = make_reader(f)
        for schema, channel, message in reader.iter_messages(topics=["/joint_states"]):
            t_ns = message.publish_time
            timestamps.append(t_ns / 1e9)

            # CDR deserialize - simplified extraction of float64 arrays
            # JointState: Header header, string[] name, float64[] position, float64[] velocity, float64[] effort
            data = message.data
            # Skip CDR header (4 bytes) + Header (stamp + frame_id)
            # This is a simplified parser — just grab the position values
            if not positions_list:
                # First message — we'll use it to figure out the structure
                pass
            # For now just count messages
            positions_list.append(t_ns)

    return timestamps, len(positions_list)


def extract_wrench(mcap_path: str):
    """Extract force/torque data from /fts_broadcaster/wrench topic."""
    timestamps = []
    forces = []

    with open(mcap_path, "rb") as f:
        reader = make_reader(f)
        for schema, channel, message in reader.iter_messages(
            topics=["/fts_broadcaster/wrench"]
        ):
            t_ns = message.publish_time
            timestamps.append(t_ns / 1e9)
            # CDR format — wrench is after header
            # WrenchStamped: Header header, Wrench wrench
            # Wrench: Vector3 force, Vector3 torque
            # Each Vector3 = 3x float64
            data = message.data
            # Skip CDR encapsulation (4 bytes) + Header (4+4+4+string)
            # Find the force data by looking for the pattern
            # Simplified: just extract the last 48 bytes (6 float64s = force xyz + torque xyz)
            if len(data) >= 52:
                # Try offset — CDR header(4) + stamp(8) + frame_id_len(4) + frame_id + padding + wrench(48)
                # Force is 3 float64s starting at some offset
                try:
                    # Find approximate offset — look for reasonable force values
                    offset = len(data) - 48
                    fx, fy, fz, tx, ty, tz = struct.unpack_from("<6d", data, offset)
                    forces.append((fx, fy, fz))
                except Exception:
                    pass

    return timestamps, forces


def main():
    parser = argparse.ArgumentParser(description="AIC Bag File Reader")
    parser.add_argument("bag_dir", help="Path to bag directory (containing .mcap file)")
    parser.add_argument("--plot", action="store_true", help="Plot force data (requires matplotlib)")
    parser.add_argument("--list-all", action="store_true", help="List all bag directories in aic_results")
    args = parser.parse_args()

    if args.list_all:
        results_dir = Path.home() / "projects/Project-Automaton/aic_results"
        print(f"\nBag directories in {results_dir}:")
        for d in sorted(results_dir.iterdir()):
            if d.is_dir() and list(d.glob("*.mcap")):
                mcap = list(d.glob("*.mcap"))[0]
                size_mb = mcap.stat().st_size / 1e6
                print(f"  {d.name}  ({size_mb:.0f} MB)")
        return

    mcap_path = find_mcap_file(args.bag_dir)

    # Print summary
    print_summary(mcap_path)

    # Extract and show force data
    timestamps, forces = extract_wrench(mcap_path)
    if forces:
        t0 = timestamps[0]
        print(f"\n{'='*60}")
        print(f"FORCE/TORQUE DATA ({len(forces)} samples)")
        print(f"{'='*60}")
        print(f"{'Time (s)':<10} {'Fx (N)':<12} {'Fy (N)':<12} {'Fz (N)':<12} {'|F| (N)':<12}")
        print(f"{'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*12}")

        # Print every 10th sample to keep output manageable
        step = max(1, len(forces) // 20)
        for i in range(0, len(forces), step):
            t = timestamps[i] - t0
            fx, fy, fz = forces[i]
            mag = (fx**2 + fy**2 + fz**2) ** 0.5
            print(f"{t:<10.2f} {fx:<12.2f} {fy:<12.2f} {fz:<12.2f} {mag:<12.2f}")

        # Max force
        max_force = max(forces, key=lambda f: (f[0]**2 + f[1]**2 + f[2]**2) ** 0.5)
        max_mag = (max_force[0]**2 + max_force[1]**2 + max_force[2]**2) ** 0.5
        print(f"\nMax force magnitude: {max_mag:.2f} N")

    if args.plot and forces:
        try:
            import matplotlib
            matplotlib.use("Agg")  # Non-interactive backend for WSL2
            import matplotlib.pyplot as plt

            t0 = timestamps[0]
            times = [t - t0 for t in timestamps[: len(forces)]]
            fx_vals = [f[0] for f in forces]
            fy_vals = [f[1] for f in forces]
            fz_vals = [f[2] for f in forces]
            mag_vals = [(f[0]**2 + f[1]**2 + f[2]**2) ** 0.5 for f in forces]

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

            ax1.plot(times, fx_vals, label="Fx", alpha=0.8)
            ax1.plot(times, fy_vals, label="Fy", alpha=0.8)
            ax1.plot(times, fz_vals, label="Fz", alpha=0.8)
            ax1.set_ylabel("Force (N)")
            ax1.set_title("Force Components Over Time")
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            ax2.plot(times, mag_vals, label="|F|", color="red", alpha=0.8)
            ax2.axhline(y=20, color="orange", linestyle="--", label="20N penalty threshold")
            ax2.set_xlabel("Time (s)")
            ax2.set_ylabel("Force Magnitude (N)")
            ax2.set_title("Force Magnitude (>20N for >1s = penalty)")
            ax2.legend()
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()
            # Save to home dir if bag_dir isn't writable
            out_path = Path(args.bag_dir) / "force_plot.png"
            try:
                with open(out_path, "wb") as test:
                    pass
            except PermissionError:
                out_path = Path.home() / "projects/Project-Automaton/aic_results" / (Path(args.bag_dir).name + "_force_plot.png")
            plt.savefig(out_path, dpi=150)
            print(f"\nPlot saved to: {out_path}")

        except ImportError:
            print("\nmatplotlib not available. Install it for plotting support.")


if __name__ == "__main__":
    main()
