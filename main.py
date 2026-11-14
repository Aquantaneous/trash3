from dataclasses import dataclass
import math
from drafter import *

set_website_title("Tank Ballistics Calculator")
set_site_information(
    author="Kasper Milton",
    description="Use or create your own ammunition and armor presets to see how the shell performs.",
    sources="Thanks to the Drafter docs and my study group.",
    planning=["planning.pdf"],
    links=["https://github.com/Aquantaneous/CS108-Final-Project"]
)
hide_debug_information()
set_website_framed(False)


# ==========================================
# GLOBAL CONSTANTS
# ==========================================
RHO_STEEL = 7850.0       # Density of Rolled Homogeneous Armor (kg/m^3)
RHO_COPPER = 8960.0      # Density of copper HEAT liner (kg/m^3)
RHO_TUNGSTEN = 17500.0   # Density of tungsten APFSDS rod (kg/m^3)
RHO_AIR = 1.225          # Standard air density at sea level (kg/m^3)
DEMARRE_K = 0.00012      # Empirical DeMarre coefficient for APCBC
ARMOR_YIELD_PA = 1.5e9   # Approximate RHA yield strength (Pa)


# ==========================================
# DATACLASSES
# ==========================================
@dataclass
class Shell:
    """Represents a tank projectile and its physical properties."""
    name: str
    shell_type: str
    mass: float
    diameter: float
    muzzle_velocity: float
    length: float


@dataclass
class Target:
    """Represents a target armor plate's thickness, slope, and ERA status."""
    thickness_mm: float
    angle_deg: float
    has_era: bool


@dataclass
class State:
    """Stores persistent application state across all simulator routes."""
    active_shell: Shell
    arsenal: list[Shell]
    target: Target
    simulation_distance: float
    last_verdict: str


# ==========================================
# HELPER PHYSICS FUNCTIONS
# ==========================================
def calculate_velocity_decay(shell: Shell, distance: float) -> float:
    """
    Calculates projectile impact velocity after aerodynamic drag over a
    given distance using exponential velocity decay.

    Args:
        shell (Shell): The tank shell being fired.
        distance (float): Engagement distance in meters.
    Returns:
        float: The impact velocity in meters per second (m/s).
    """
    if distance <= 0:
        return shell.muzzle_velocity
    area = math.pi * ((shell.diameter / 2.0) ** 2)
    drag_coeff = 0.18 if shell.shell_type == "APFSDS" else 0.28
    k = (RHO_AIR * drag_coeff * area) / (2.0 * shell.mass)
    return shell.muzzle_velocity * math.exp(-k * distance)


def calculate_penetration(shell: Shell, impact_velocity: float,
                          has_era: bool) -> float:
    """
    Calculates raw flat Rolled Homogeneous Armor (RHA) penetration in
    millimeters based on the projectile's warhead type and target ERA.

    Args:
        shell (Shell): The tank shell impacting the armor.
        impact_velocity (float): Velocity at the moment of impact in m/s.
        has_era (bool): Whether Explosive Reactive Armor is equipped.
    Returns:
        float: Flat armor penetration depth in millimeters (mm).
    """
    # Meaningful If Statement #1: Branching equations by warhead type
    if shell.shell_type == "APCBC":
        energy_term = (shell.mass * (impact_velocity ** 2)) / (
            shell.diameter ** 3
        )
        pen_m = DEMARRE_K * (energy_term ** 0.7) * shell.diameter
        pen_mm = pen_m * 1000.0
    elif shell.shell_type == "APFSDS":
        rod_length_mm = shell.length * 1000.0
        density_ratio = math.sqrt(RHO_TUNGSTEN / RHO_STEEL)
        exponent = -ARMOR_YIELD_PA / (RHO_TUNGSTEN * (impact_velocity ** 2))
        velocity_factor = math.exp(exponent)
        pen_mm = rod_length_mm * density_ratio * velocity_factor
    else:
        jet_length_mm = shell.length * 1000.0 * 3.5
        pen_mm = jet_length_mm * math.sqrt(RHO_COPPER / RHO_STEEL)

    if has_era:
        if shell.shell_type == "HEAT":
            pen_mm *= 0.45
        else:
            pen_mm *= 0.80

    return pen_mm


def evaluate_shot(shell: Shell, target: Target,
                  distance: float) -> tuple[float, float, float, str]:
    """
    Runs a complete terminal ballistics evaluation of a shell against a
    target at a specified range, checking for ricochets and armor defeat.

    Args:
        shell (Shell): The projectile being evaluated.
        target (Target): The target armor configuration.
        distance (float): Engagement distance in meters.
    Returns:
        tuple[float, float, float, str]: A tuple containing impact velocity,
            flat penetration (mm), line-of-sight armor (mm), and verdict text.
    """
    v_impact = calculate_velocity_decay(shell, distance)
    pen_mm = calculate_penetration(shell, v_impact, target.has_era)

    clamped_angle = min(max(target.angle_deg, 0.0), 85.0)
    los_mm = target.thickness_mm / math.cos(math.radians(clamped_angle))

    # Meaningful If Statement #2: Ricochet angle check
    if clamped_angle > 72.0 and shell.shell_type != "HEAT":
        verdict = "RICOCHET (Impact angle exceeded 72 degrees)"
    # Meaningful If Statement #3: Armor defeat comparison
    elif pen_mm >= los_mm:
        margin = pen_mm - los_mm
        verdict = f"PENETRATION SUCCESSFUL (+{margin:.1f} mm overpenetration)"
    else:
        deficit = los_mm - pen_mm
        verdict = f"ARMOR STOPPED ROUND (-{deficit:.1f} mm short)"

    return v_impact, pen_mm, los_mm, verdict


def create_default_arsenal() -> list[Shell]:
    """
    Creates and returns the default list of historical and modern tank
    shells used to initialize or reset the simulator.

    Args:
        None
    Returns:
        list[Shell]: A list of four preset Shell instances.
    """
    return [
        Shell("120mm M829A2", "APFSDS", 7.9, 0.120, 1680.0, 0.65),
        Shell("120mm M830A1", "HEAT", 11.4, 0.120, 1140.0, 0.14),
        Shell("88mm PzGr. 39/43", "APCBC", 10.2, 0.088, 1000.0, 0.35),
        Shell("125mm 3BM42 Mango", "APFSDS", 7.05, 0.125, 1700.0, 0.57)
    ]


# ==========================================
# ROUTES & PAGES (12 Routes, 7 Distinct Pages)
# ==========================================
@route
def index(state: State) -> Page:
    """
    Renders the main dashboard page displaying the current session
    loadout and navigation buttons to all simulator tools.

    Args:
        state (State): The current application state.
    Returns:
        Page: The home dashboard page.
    """
    era_status = "Enabled" if state.target.has_era else "Disabled"
    active_line = (
        f"Active Shell: {state.active_shell.name} "
        f"({state.active_shell.shell_type})"
    )
    target_line = (
        f"Target Profile: {state.target.thickness_mm:.0f} mm RHA @ "
        f"{state.target.angle_deg:.0f}° | ERA: {era_status}"
    )
    return Page(state, [
        Header("Tank Ballistics & Terminal Penetration Simulator"),
        Text("Configure ammunition, adjust armor, and run simulations."),
        LineBreak(),
        Header("Current Session Loadout", 2),
        Text(active_line),
        LineBreak(),
        Text(target_line),
        LineBreak(),
        Text(f"Engagement Range: {state.simulation_distance:.0f} m"),
        LineBreak(),
        Text(f"Last Simulation Result: {state.last_verdict}"),
        LineBreak(),
        LineBreak(),
        Button("1. Manage Shell Arsenal", show_arsenal),
        Button("2. Configure Target Armor", target_config),
        Button("3. Run Ballistics Simulator", simulate_page),
        Button("4. Compare Entire Arsenal", compare_arsenal),
        Button("5. Mission Summary Report", summary_report)
    ])


@route
def show_arsenal(state: State, new_name: str = "", new_type: str = "",
                 new_mass: str = "", new_diameter: str = "",
                 new_velocity: str = "", new_length: str = "") -> Page:
    """
    Renders the shell arsenal inventory table with kinetic energy values
    and buttons to select an active shell or add a new custom shell.
    Optional parameters absorb unused form fields when Cancel is clicked.

    Args:
        state (State): The current application state.
        new_name (str): Optional unused form input from add_shell_page.
        new_type (str): Optional unused form input from add_shell_page.
        new_mass (str): Optional unused form input from add_shell_page.
        new_diameter (str): Optional unused form input from add_shell_page.
        new_velocity (str): Optional unused form input from add_shell_page.
        new_length (str): Optional unused form input from add_shell_page.
    Returns:
        Page: The shell arsenal inventory page.
    """
    rows = [[
        "Shell Name", "Type", "Mass", "Caliber",
        "Muzzle Vel.", "Muzzle Energy", "Status"
    ]]

    # Advanced technique: enumerate() pairs each Shell instance with its list
    # index, and Argument() passes that index to select_shell on click.
    for i, shell in enumerate(state.arsenal):
        ke_mj = (0.5 * shell.mass * (shell.muzzle_velocity ** 2)) / 1_000_000.0
        if shell.name == state.active_shell.name:
            action_cell = "ACTIVE"
        else:
            action_cell = Button(
                "Select",
                select_shell,
                arguments=Argument("shell_idx", i)
            )

        rows.append([
            shell.name,
            shell.shell_type,
            f"{shell.mass:.1f} kg",
            f"{shell.diameter * 1000:.0f} mm",
            f"{shell.muzzle_velocity:.0f} m/s",
            f"{ke_mj:.2f} MJ",
            action_cell
        ])

    return Page(state, [
        Header("Tank Shell Arsenal"),
        Text("Select an active shell or add custom ammunition below."),
        Table(rows),
        LineBreak(),
        Button("+ Add Custom Shell", add_shell_page),
        Button("Back to Home", index)
    ])


@route
def select_shell(state: State, shell_idx: int) -> Page:
    """
    Updates the active shell in the state based on the selected index
    and returns to the arsenal page.

    Args:
        state (State): The current application state.
        shell_idx (int): Index of the chosen shell in state.arsenal.
    Returns:
        Page: The updated shell arsenal page.
    """
    idx = int(shell_idx)
    if 0 <= idx < len(state.arsenal):
        state.active_shell = state.arsenal[idx]
    return show_arsenal(state)


@route
def add_shell_page(state: State) -> Page:
    """
    Renders a form allowing the user to input specifications for a new
    custom tank shell.

    Args:
        state (State): The current application state.
    Returns:
        Page: The custom shell creation form page.
    """
    return Page(state, [
        Header("Add Custom Tank Shell"),
        Text("Shell Name:"),
        TextBox("new_name", "120mm DM53"),
        LineBreak(),
        Text("Warhead Type:"),
        SelectBox("new_type", ["APFSDS", "APCBC", "HEAT"], "APFSDS"),
        LineBreak(),
        Text("Projectile Mass (kg):"),
        TextBox("new_mass", "8.35"),
        LineBreak(),
        Text("Projectile Diameter (meters, e.g., 0.120):"),
        TextBox("new_diameter", "0.120"),
        LineBreak(),
        Text("Muzzle Velocity (m/s):"),
        TextBox("new_velocity", "1750"),
        LineBreak(),
        Text("Penetrator Rod / Liner Length (meters, e.g., 0.68):"),
        TextBox("new_length", "0.68"),
        LineBreak(),
        Button("Save Shell to Arsenal", save_shell),
        Button("Cancel", show_arsenal)
    ])


@route
def save_shell(state: State, new_name: str, new_type: str, new_mass: str,
               new_diameter: str, new_velocity: str, new_length: str) -> Page:
    """
    Validates user inputs, creates a new Shell instance, appends it to the
    arsenal, sets it as the active shell, and returns to the arsenal page.

    Args:
        state (State): The current application state.
        new_name (str): Name of the custom shell.
        new_type (str): Warhead type ('APFSDS', 'APCBC', or 'HEAT').
        new_mass (str): Mass in kilograms as text input.
        new_diameter (str): Diameter in meters as text input.
        new_velocity (str): Muzzle velocity in m/s as text input.
        new_length (str): Penetrator or liner length in meters as text input.
    Returns:
        Page: The updated shell arsenal page.
    """
    # Advanced technique: try/except ValueError safely catches invalid
    # text inputs when converting strings to floats without crashing.
    try:
        mass_val = max(0.1, float(new_mass))
        diam_val = max(0.01, float(new_diameter))
        vel_val = max(50.0, float(new_velocity))
        len_val = max(0.05, float(new_length))
        clean_name = new_name.strip() if new_name.strip() else "Custom Round"

        custom_shell = Shell(
            name=clean_name,
            shell_type=new_type,
            mass=mass_val,
            diameter=diam_val,
            muzzle_velocity=vel_val,
            length=len_val
        )
        state.arsenal.append(custom_shell)
        state.active_shell = custom_shell
    except ValueError:
        pass

    return show_arsenal(state)


@route
def target_config(state: State) -> Page:
    """
    Renders the target armor configuration page where users can adjust
    armor thickness, slope angle, and Explosive Reactive Armor (ERA).

    Args:
        state (State): The current application state.
    Returns:
        Page: The target armor configuration page.
    """
    return Page(state, [
        Header("Target Armor Configuration"),
        Text(f"Currently Testing Against: {state.active_shell.name}"),
        LineBreak(),
        Text("Base RHA Armor Thickness (mm):"),
        TextBox("armor_mm", str(state.target.thickness_mm)),
        LineBreak(),
        Text("Armor Slope Angle (degrees from vertical, 0 to 85):"),
        TextBox("angle_deg", str(state.target.angle_deg)),
        LineBreak(),
        CheckBox("has_era", state.target.has_era),
        Text("Equip Target with Explosive Reactive Armor (ERA)"),
        LineBreak(),
        Button("Apply Target Specs", update_target),
        Button("Back to Home", index)
    ])


@route
def update_target(state: State, armor_mm: str, angle_deg: str,
                  has_era: bool) -> Page:
    """
    Validates target armor inputs, updates state.target with a new Target
    instance, and redirects to the ballistics simulator page.

    Args:
        state (State): The current application state.
        armor_mm (str): Base armor thickness in millimeters as text input.
        angle_deg (str): Armor slope angle in degrees as text input.
        has_era (bool): Whether ERA protection is enabled.
    Returns:
        Page: The ballistics simulator page.
    """
    # Advanced technique: try/except ValueError ignores non-numeric user
    # inputs and preserves existing valid target values.
    try:
        thick = max(1.0, float(armor_mm))
        angle = min(max(0.0, float(angle_deg)), 85.0)
        state.target = Target(
            thickness_mm=thick,
            angle_deg=angle,
            has_era=has_era
        )
    except ValueError:
        pass
    return simulate_page(state)


@route
def simulate_page(state: State) -> Page:
    """
    Renders the terminal ballistics simulator page showing current impact
    physics, outcome verdict, and a multi-range penetration drop-off table.

    Args:
        state (State): The current application state.
    Returns:
        Page: The terminal ballistics simulator page.
    """
    v_imp, pen, los, verdict = evaluate_shot(
        state.active_shell, state.target, state.simulation_distance
    )

    range_rows = [["Range (m)", "Impact Velocity", "Effective Penetration"]]
    for dist in [100, 500, 1000, 1500, 2000, 3000]:
        d_vel = calculate_velocity_decay(state.active_shell, float(dist))
        d_pen = calculate_penetration(
            state.active_shell, d_vel, state.target.has_era
        )
        range_rows.append([f"{dist} m", f"{d_vel:.0f} m/s", f"{d_pen:.1f} mm"])

    shell_text = (
        f"Active Shell: {state.active_shell.name} "
        f"({state.active_shell.shell_type})"
    )
    target_text = (
        f"Target Armor: {state.target.thickness_mm:.0f} mm @ "
        f"{state.target.angle_deg:.0f}° (Line-of-Sight: {los:.1f} mm)"
    )

    return Page(state, [
        Header("Terminal Ballistics Simulator"),
        Text(shell_text),
        LineBreak(),
        Text(target_text),
        LineBreak(),
        Text("Engagement Distance (meters):"),
        TextBox("dist_input", str(state.simulation_distance)),
        Button("Calculate Impact Physics", run_sim),
        LineBreak(),
        Header("Simulation Output", 2),
        Text(f"Velocity at Impact: {v_imp:.1f} m/s"),
        LineBreak(),
        Text(f"Calculated Penetration: {pen:.1f} mm RHA"),
        LineBreak(),
        Text(f"Outcome Verdict: {verdict}"),
        LineBreak(),
        Header("Penetration Drop-off by Distance", 2),
        Table(range_rows),
        LineBreak(),
        Button("Compare All Arsenal Shells", compare_arsenal),
        Button("Back to Home", index)
    ])


@route
def run_sim(state: State, dist_input: str) -> Page:
    """
    Updates the simulation engagement distance and stores the latest
    penetration verdict in state before re-rendering the simulator page.

    Args:
        state (State): The current application state.
        dist_input (str): Engagement range in meters as text input.
    Returns:
        Page: The updated ballistics simulator page.
    """
    # Advanced technique: try/except ValueError prevents server crashes
    # when non-numeric text is entered into the distance field.
    try:
        dist = max(0.0, float(dist_input))
        state.simulation_distance = dist
        _, _, _, verdict = evaluate_shot(
            state.active_shell, state.target, dist
        )
        state.last_verdict = verdict
    except ValueError:
        pass
    return simulate_page(state)


@route
def compare_arsenal(state: State) -> Page:
    """
    Evaluates every shell in state.arsenal against the current target at
    the active engagement range and displays a comparison table.

    Args:
        state (State): The current application state.
    Returns:
        Page: The comparative arsenal analysis page.
    """
    pen_col = f"Penetration @ {state.simulation_distance:.0f}m"
    rows = [["Shell Name", "Type", pen_col, "Target LOS Armor", "Result"]]

    for shell in state.arsenal:
        _, pen, los, verdict = evaluate_shot(
            shell, state.target, state.simulation_distance
        )
        rows.append([
            shell.name,
            shell.shell_type,
            f"{pen:.1f} mm",
            f"{los:.1f} mm",
            verdict
        ])

    return Page(state, [
        Header("Comparative Arsenal Analysis"),
        Text(f"Testing all stored shells at {state.simulation_distance:.0f} m."),
        Table(rows),
        LineBreak(),
        Button("Reconfigure Target", target_config),
        Button("View Mission Summary", summary_report),
        Button("Back to Home", index)
    ])


@route
def summary_report(state: State) -> Page:
    """
    Displays a formatted operational summary report of the current shell,
    velocity decay, armor overmatch, and final verdict, with a reset option.

    Args:
        state (State): The current application state.
    Returns:
        Page: The ballistics operational summary page.
    """
    v_imp, pen, los, verdict = evaluate_shot(
        state.active_shell, state.target, state.simulation_distance
    )
    velocity_loss = state.active_shell.muzzle_velocity - v_imp

    proj_line = (
        f"Selected Projectile: {state.active_shell.name} "
        f"({state.active_shell.shell_type})"
    )
    vel_line = (
        f"Aerodynamic Velocity Loss: {velocity_loss:.1f} m/s over "
        f"{state.simulation_distance:.0f} m"
    )
    pen_line = (
        f"Effective Penetration: {pen:.1f} mm vs "
        f"{los:.1f} mm Effective Armor"
    )

    return Page(state, [
        Header("Ballistics Operational Summary"),
        Text(f"Total Shells in Arsenal: {len(state.arsenal)}"),
        LineBreak(),
        Text(proj_line),
        LineBreak(),
        Text(vel_line),
        LineBreak(),
        Text(pen_line),
        LineBreak(),
        Text(f"Final Assessment: {verdict}"),
        LineBreak(),
        LineBreak(),
        Button("Reset Simulator to Defaults", reset_state),
        Button("Return to Home", index)
    ])


@route
def reset_state(state: State) -> Page:
    """
    Resets all state fields back to their initial default values and
    returns to the home dashboard.

    Args:
        state (State): The current application state.
    Returns:
        Page: The home dashboard page with reset state.
    """
    default_shells = create_default_arsenal()
    state.arsenal = default_shells
    state.active_shell = default_shells[0]
    state.target = Target(thickness_mm=450.0, angle_deg=60.0, has_era=False)
    state.simulation_distance = 1000.0
    state.last_verdict = "Not yet simulated"
    return index(state)


# ==========================================
# UNIT TESTS (Helpers & All 12 Routes)
# ==========================================
def build_test_state() -> State:
    """
    Constructs a fresh default State instance for isolated unit testing.

    Args:
        None
    Returns:
        State: A clean State object initialized with default values.
    """
    shells = create_default_arsenal()
    return State(
        active_shell=shells[0],
        arsenal=shells,
        target=Target(thickness_mm=450.0, angle_deg=60.0, has_era=False),
        simulation_distance=1000.0,
        last_verdict="Ready to simulate"
    )


# --- Helper Function Unit Tests ---
assert_equal(len(create_default_arsenal()), 4)

test_apfsds = Shell("Test APFSDS", "APFSDS", 8.0, 0.120, 1700.0, 0.65)
test_heat = Shell("Test HEAT", "HEAT", 11.0, 0.120, 1100.0, 0.15)
test_apcbc = Shell("Test APCBC", "APCBC", 10.0, 0.088, 1000.0, 0.35)

assert_equal(calculate_velocity_decay(test_apfsds, 0.0), 1700.0)
assert_equal(round(calculate_velocity_decay(test_apfsds, 1000.0), 2), 1454.65)
assert_equal(round(calculate_penetration(test_heat, 1100.0, False), 2), 560.89)
assert_equal(round(calculate_penetration(test_heat, 500.0, False), 2), 560.89)
assert_equal(round(calculate_penetration(test_heat, 1100.0, True), 2), 252.4)
assert_equal(round(calculate_penetration(test_apcbc, 1000.0, False), 2), 138118.01)

ricochet_target = Target(thickness_mm=100.0, angle_deg=75.0, has_era=False)
_, _, _, ricochet_verdict = evaluate_shot(test_apfsds, ricochet_target, 500.0)
assert_equal(ricochet_verdict, "RICOCHET (Impact angle exceeded 72 degrees)")

# --- Route Unit Tests (All 12 Routes) ---
# 1. Test index
s1 = build_test_state()
assert_equal(isinstance(index(s1), Page), True)

# 2. Test show_arsenal
s2 = build_test_state()
assert_equal(isinstance(show_arsenal(s2), Page), True)

# 3. Test select_shell (State modification #1: active_shell)
s3 = build_test_state()
select_shell(s3, 2)
assert_equal(s3.active_shell.name, "88mm PzGr. 39/43")

# 4. Test add_shell_page
s4 = build_test_state()
assert_equal(isinstance(add_shell_page(s4), Page), True)

# 5. Test save_shell (State modification #2: arsenal list & active_shell)
s5 = build_test_state()
save_shell(s5, "120mm DM53", "APFSDS", "8.35", "0.120", "1750", "0.68")
assert_equal(len(s5.arsenal), 5)
assert_equal(s5.active_shell.name, "120mm DM53")

# 6. Test target_config
s6 = build_test_state()
assert_equal(isinstance(target_config(s6), Page), True)

# 7. Test update_target (State modification #3: target dataclass)
s7 = build_test_state()
update_target(s7, "600", "45", True)
assert_equal(s7.target.thickness_mm, 600.0)
assert_equal(s7.target.angle_deg, 45.0)
assert_equal(s7.target.has_era, True)

# 8. Test simulate_page
s8 = build_test_state()
assert_equal(isinstance(simulate_page(s8), Page), True)

# 9. Test run_sim (State modification #4 & #5: simulation_distance & last_verdict)
s9 = build_test_state()
run_sim(s9, "2000")
assert_equal(s9.simulation_distance, 2000.0)
assert_equal("ARMOR STOPPED ROUND" in s9.last_verdict, False)

# 10. Test compare_arsenal
s10 = build_test_state()
assert_equal(isinstance(compare_arsenal(s10), Page), True)

# 11. Test summary_report
s11 = build_test_state()
assert_equal(isinstance(summary_report(s11), Page), True)

# 12. Test reset_state
s12 = build_test_state()
s12.simulation_distance = 2500.0
reset_state(s12)
assert_equal(s12.simulation_distance, 1000.0)
assert_equal(s12.last_verdict, "Not yet simulated")


# ==========================================
# INITIALIZATION & SERVER START
# ==========================================
initial_arsenal = create_default_arsenal()
initial_state = State(
    active_shell=initial_arsenal[0],
    arsenal=initial_arsenal,
    target=Target(thickness_mm=450.0, angle_deg=60.0, has_era=False),
    simulation_distance=1000.0,
    last_verdict="Ready to simulate"
)

start_server(initial_state, port=8100)
