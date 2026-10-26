
try {
    foreach lib [split $::env(HW2_LIBS) \n] { read_liberty $lib }
    read_verilog $::env(HW2_ROOT)/src/rsz/test/gcd_asap7_cts.v
    link_design gcd
    source $::env(HW2_ROOT)/test/flow_helpers.tcl
    read_sdc $::env(HW2_ROOT)/test/gcd_asap7.sdc
    set_cmd_units -time ns
    create_clock -name core_clock -period $::env(HW2_PERIOD) [get_ports clk]
    set_operating_conditions -analysis_type on_chip_variation
    set_propagated_clock [all_clocks]
    set_clock_latency -source 0 [all_clocks]
    set_clock_uncertainty 0 [all_clocks]
    set_timing_derate -early -cell_delay 0.9
    set_timing_derate -late -cell_delay 1.1
    sta::set_crpr_mode same_transition
    set input [open $::env(HW2_PAIRS) r]
    set lines [split [string trim [read $input]] \n]
    close $input
    foreach enabled {0 1} {
        sta::set_crpr_enabled $enabled
        set index 0
        foreach line $lines {
            lassign [split $line \t] launch endpoint
            set clock_pin "[file dirname $launch]/CLK"
            set stem "$::env(HW2_OUT)/pair_${index}_cppr_${enabled}"
            report_checks -from [get_pins $clock_pin] -through [get_pins $launch] \
                -to [get_pins $endpoint] -path_delay max \
                -format full_clock_expanded -digits 9 > ${stem}.txt
            report_checks -from [get_pins $clock_pin] -through [get_pins $launch] \
                -to [get_pins $endpoint] -path_delay max -format json > ${stem}.json
            incr index
        }
    }
} on error {message options} {
    puts stderr $message
    exit 1
}
exit 0
