// Preserve established C symbols for existing UVMF DPI integrations.
// Driver DPI Calls
import "DPI-C" context function void C_configure(
  input string path,
  input c_bit_array_t bit_vec
);
import "DPI-C" context function void C_do_response_ready(
  input string path,
  input c_bit_array_t bit_vec
);
import "DPI-C" context task C_access(
  input string path,
  inout c_bit_array_t bit_vec
);
import "DPI-C" context task C_response(
  input string path,
  inout c_bit_array_t bit_vec
);

// Monitor DPI Calls
import "DPI-C" context function void C_start_monitoring(input string path);
import "DPI-C" context task C_wait_for_reset(input string path);
import "DPI-C" context task C_wait_for_num_clocks(
  input string path,
  input c_bit_array_t bit_vec
);
import "DPI-C" context function void C_initialize_monitor(input string path);
