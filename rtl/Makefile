IVERILOG ?= iverilog
VVP ?= vvp
BUILD_DIR := build

.PHONY: test clean

test: $(BUILD_DIR)/timestamp_unwrapper.vvp $(BUILD_DIR)/timestamp_normalizer.vvp $(BUILD_DIR)/sequence_order_guard.vvp
	$(VVP) $(BUILD_DIR)/timestamp_unwrapper.vvp
	$(VVP) $(BUILD_DIR)/timestamp_normalizer.vvp
	$(VVP) $(BUILD_DIR)/sequence_order_guard.vvp

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/timestamp_unwrapper.vvp: timestamp_unwrapper.sv tb/tb_timestamp_unwrapper.sv | $(BUILD_DIR)
	$(IVERILOG) -g2012 -s tb_timestamp_unwrapper -o $@ $^

$(BUILD_DIR)/timestamp_normalizer.vvp: timestamp_normalizer.sv tb/tb_timestamp_normalizer.sv | $(BUILD_DIR)
	$(IVERILOG) -g2012 -s tb_timestamp_normalizer -o $@ $^

$(BUILD_DIR)/sequence_order_guard.vvp: sequence_order_guard.sv tb/tb_sequence_order_guard.sv | $(BUILD_DIR)
	$(IVERILOG) -g2012 -s tb_sequence_order_guard -o $@ $^

clean:
	rm -rf $(BUILD_DIR)
