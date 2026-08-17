module dut
#(
    integer G_REGWIDTH = 32,
    integer G_ADDR_WIDTH = 3
)
(
    input wire clk,
    input wire rst,

    input wire s_obi_req,
    output logic s_obi_gnt,
    input wire [G_ADDR_WIDTH-1:0] s_obi_addr,
    input wire s_obi_we,
    input wire [(G_REGWIDTH/8)-1:0] s_obi_be,
    input wire [G_REGWIDTH-1:0] s_obi_wdata,
    input wire [0:0] s_obi_aid,
    output logic s_obi_rvalid,
    input wire s_obi_rready,
    output logic [G_REGWIDTH-1:0] s_obi_rdata,
    output logic s_obi_err,
    output logic [0:0] s_obi_rid
);

logic w_start;
logic f_busy;
logic d_busy;
logic [3:0] f_cnt;
logic [3:0] d_cnt;


    regblock i_regblock (
        .*
        ,.hwif_out_start(w_start)
        ,.hwif_in_busy(f_busy)
    );

    always @(*) begin : p_sm
        d_busy = f_busy;
        d_cnt = f_cnt;
        if (0 == f_cnt) d_busy = 0;
        if (w_start) begin
            d_busy = 1;
            d_cnt = 15;
        end
        if (f_busy) d_cnt = f_cnt - 1;
    end

    always @(posedge clk) begin : p_reg
        if (rst) begin
            f_busy <= 0;
            f_cnt <= 0;
        end else begin
            f_busy <= d_busy;
            f_cnt <= d_cnt;
        end
    end

endmodule
